"""Источники зависимостей: репозиторий Maven и файл тестового репозитория.

У обоих источников одинаковый набор методов: root, dependencies и
label. Поэтому алгоритм обхода графа не зависит от того, откуда
берутся данные.
"""
import re

from depviz.errors import DepVizError
from depviz.maven import MavenRepository, RepositoryError

TEST_NAME = re.compile(r"^[A-Z]+$")
UNRESOLVED = "${"


class TestRepoError(DepVizError):
    """Ошибка в файле тестового репозитория."""


def parse_test_line(text, number):
    """Разобрать строку 'A: B C' в (пакет, [зависимости])."""
    name, colon, rest = text.partition(":")
    name = name.strip()
    deps = rest.split()
    if not colon:
        raise TestRepoError(f"line {number}: expected 'NAME: DEPS'")
    for item in [name] + deps:
        if not TEST_NAME.match(item):
            raise TestRepoError(
                f"line {number}: bad package name '{item}' (A-Z only)")
    return name, deps


def load_test_repo(path):
    """Прочитать файл тестового репозитория в словарь пакет -> список."""
    try:
        with open(path, encoding="utf-8") as file:
            lines = file.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise TestRepoError(f"cannot read test repository: {exc}") from None
    graph = {}
    for number, text in enumerate(lines, start=1):
        text = text.split("#", 1)[0].strip()
        if not text:
            continue
        name, deps = parse_test_line(text, number)
        if name in graph:
            raise TestRepoError(f"line {number}: package {name} repeated")
        graph[name] = deps
    return graph


def unique(items):
    """Убрать повторы, сохранив порядок."""
    return list(dict.fromkeys(items))


class FileSource:
    """Тестовый репозиторий: пакеты — большие латинские буквы."""

    def __init__(self, path):
        """Загрузить граф из файла."""
        self.graph = load_test_repo(path)
        self.warnings = []

    def root(self, name, _version):
        """Корень графа; версия в тестовом режиме не используется."""
        known = set(self.graph).union(*self.graph.values())
        if name not in known:
            raise TestRepoError(f"package {name} not found in test repository")
        return name

    def dependencies(self, node):
        """Прямые зависимости пакета."""
        return unique(self.graph.get(node, []))

    @staticmethod
    def label(node):
        """Подпись вершины."""
        return node


class MavenSource:
    """Настоящий репозиторий Maven: вершина — пара (имя, версия)."""

    def __init__(self, url, fetch=None):
        """Создать доступ к репозиторию по URL."""
        self.repository = MavenRepository(url, fetch) if fetch else \
            MavenRepository(url)
        self.warnings = self.repository.warnings

    def root(self, name, version):
        """Проверить, что POM пакета есть, и вернуть корень."""
        group, artifact = name.split(":")
        self.repository.pom((group, artifact, version))
        return (name, version)

    def dependencies(self, node):
        """Прямые зависимости (имя, версия); ошибки — в предупреждения."""
        name, version = node
        group, artifact = name.split(":")
        try:
            deps = self.repository.direct_dependencies(group, artifact,
                                                       version)
        except RepositoryError as exc:
            self.warnings.append(f"{self.label(node)}: {exc}")
            return []
        result = []
        for dep in deps:
            if not dep.version or UNRESOLVED in dep.version:
                self.warnings.append(
                    f"{self.label(node)}: version of {dep.name} is unknown")
                continue
            result.append((dep.name, dep.version))
        return unique(result)

    @staticmethod
    def label(node):
        """Подпись вершины: groupId:artifactId:version."""
        return f"{node[0]}:{node[1]}"


def make_source(config):
    """Выбрать источник по параметру test_mode."""
    if config.test_mode:
        return FileSource(config.repository)
    return MavenSource(config.repository)

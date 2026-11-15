"""Получение зависимостей пакетов из репозитория Maven (файлы POM).

Каждая версия пакета в репозитории Maven описана XML-файлом POM:
{repository}/{groupId с / вместо .}/{artifactId}/{version}/
{artifactId}-{version}.pom. В нём есть список зависимостей, а также
родитель (parent), свойства (properties) и раздел dependencyManagement,
откуда берутся версии, если они не указаны прямо.
"""
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as etree
from dataclasses import dataclass, field

from depviz.errors import DepVizError

HTTP_NOT_FOUND = 404
TIMEOUT_SECONDS = 20
USER_AGENT = "depviz/1.0 (student project)"
DEFAULT_SCOPE = "compile"
USED_SCOPES = ("compile", "runtime")
IMPORT_SCOPE = "import"
PROPERTY = re.compile(r"\$\{([^}]+)\}")
MAX_SUBSTITUTIONS = 10
MAX_POM_CHAIN = 50
RANGE_START = "[("
RANGE_END = "])"
RANGE_SEPARATOR = ","


class RepositoryError(DepVizError):
    """Ошибка при получении данных из репозитория пакетов."""


class NotFoundError(RepositoryError):
    """Файл отсутствует в репозитории (HTTP 404)."""


@dataclass
class Dependency:
    """Одна зависимость пакета после подстановки свойств и версий."""

    group: str
    artifact: str
    version: str
    scope: str
    optional: bool

    @property
    def name(self):
        """Имя пакета в виде groupId:artifactId."""
        return f"{self.group}:{self.artifact}"

    def is_used(self):
        """Нужна для работы пакета: compile или runtime, не optional."""
        return self.scope in USED_SCOPES and not self.optional


@dataclass
class Pom:
    """Содержимое одного файла POM (без учёта родителей)."""

    group: str
    artifact: str
    version: str
    parent: tuple = None
    properties: dict = field(default_factory=dict)
    managed: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)


@dataclass
class Effective:
    """POM вместе со всем, что унаследовано от родителей и BOM."""

    properties: dict
    managed: dict
    dependencies: list


def pom_url(base, group, artifact, version):
    """Адрес файла POM в репозитории Maven."""
    path = group.replace(".", "/")
    return f"{base}/{path}/{artifact}/{version}/{artifact}-{version}.pom"


def download(url):
    """Скачать текст по URL средствами стандартной библиотеки."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == HTTP_NOT_FOUND:
            raise NotFoundError(f"not found: {url}") from None
        raise RepositoryError(f"HTTP error {exc.code}: {url}") from None
    except (urllib.error.URLError, OSError) as exc:
        raise RepositoryError(f"cannot reach repository: {exc}") from None


def local_name(tag):
    """Имя тега без пространства имён: {http://...}version -> version."""
    return tag.rsplit("}", 1)[-1]


def child(element, name):
    """Найти дочерний элемент по имени (или None)."""
    if element is None:
        return None
    for item in element:
        if local_name(item.tag) == name:
            return item
    return None


def text_of(element, name):
    """Текст дочернего элемента без пробелов по краям (или пустая строка)."""
    item = child(element, name)
    return (item.text or "").strip() if item is not None else ""


def read_dependencies(element):
    """Список зависимостей из блока <dependencies> как словари."""
    keys = ("groupId", "artifactId", "version", "scope", "type", "optional")
    block = child(element, "dependencies")
    if block is None:
        return []
    return [{key: text_of(item, key) for key in keys}
            for item in block if local_name(item.tag) == "dependency"]


def read_parent(root):
    """Координаты родителя (groupId, artifactId, version) или None."""
    element = child(root, "parent")
    if element is None:
        return None
    return tuple(text_of(element, key)
                 for key in ("groupId", "artifactId", "version"))


def read_properties(root):
    """Словарь свойств из блока <properties>."""
    block = child(root, "properties")
    if block is None:
        return {}
    return {local_name(item.tag): (item.text or "").strip()
            for item in block}


def parse_pom(text):
    """Разобрать XML файла POM в объект Pom."""
    try:
        root = etree.fromstring(text)
    except etree.ParseError as exc:
        raise RepositoryError(f"bad POM file: {exc}") from None
    parent = read_parent(root)
    inherited = parent or ("", "", "")
    return Pom(
        group=text_of(root, "groupId") or inherited[0],
        artifact=text_of(root, "artifactId"),
        version=text_of(root, "version") or inherited[2],
        parent=parent,
        properties=read_properties(root),
        managed=read_dependencies(child(root, "dependencyManagement")),
        dependencies=read_dependencies(root),
    )


def substitute(value, properties):
    """Подставить свойства ${имя} (с вложенными свойствами)."""
    for _ in range(MAX_SUBSTITUTIONS):
        new = PROPERTY.sub(lambda m: properties.get(m.group(1), m.group(0)),
                           value)
        if new == value:
            break
        value = new
    return value


def pick_version(version):
    """Из диапазона [1.0,2.0) взять нижнюю границу; иначе вернуть как есть."""
    if not version or version[0] not in RANGE_START:
        return version
    bounds = version.strip(RANGE_START + RANGE_END).split(RANGE_SEPARATOR)
    return next((item.strip() for item in bounds if item.strip()), "")


def project_properties(pom):
    """Встроенные свойства Maven: ${project.version} и другие."""
    props = {"project.groupId": pom.group, "project.artifactId": pom.artifact,
             "project.version": pom.version, "pom.version": pom.version,
             "version": pom.version, "pom.groupId": pom.group}
    if pom.parent:
        props["project.parent.groupId"] = pom.parent[0]
        props["project.parent.version"] = pom.parent[2]
        props["parent.version"] = pom.parent[2]
    return props


class MavenRepository:
    """Доступ к репозиторию Maven по URL с кэшем скачанных POM."""

    def __init__(self, base_url, fetch=download):
        """Запомнить адрес репозитория и функцию скачивания."""
        self.base_url = base_url.rstrip("/")
        self.fetch = fetch
        self.poms = {}
        self.done = {}
        self.warnings = []

    def pom(self, coord):
        """Скачать и разобрать POM (group, artifact, version) один раз."""
        if coord not in self.poms:
            group, artifact, version = coord
            url = pom_url(self.base_url, group, artifact, version)
            try:
                text = self.fetch(url)
            except NotFoundError:
                raise RepositoryError(
                    f"{group}:{artifact}:{version} not found in repository"
                ) from None
            self.poms[coord] = parse_pom(text)
        return self.poms[coord]

    def effective(self, coord):
        """POM с учётом родителей и импортов BOM (обход на стеке)."""
        stack = [coord]
        while stack:
            if len(stack) > MAX_POM_CHAIN:
                raise RepositoryError(f"parent chain too long for {coord}")
            top = stack[-1]
            if top in self.done:
                stack.pop()
                continue
            missing = self.missing_for(top)
            if missing:
                stack.extend(missing)
                continue
            self.done[top] = self.build_effective(top)
            stack.pop()
        return self.done[coord]

    def missing_for(self, coord):
        """Родитель или BOM, которые нужно обработать раньше этого POM."""
        pom = self.pom(coord)
        if pom.parent and pom.parent not in self.done:
            return [pom.parent]
        imports = self.import_coords(pom, self.merged_properties(pom))
        missing = []
        for item in imports:
            if item not in self.done and self.can_load(item):
                missing.append(item)
        return missing

    def can_load(self, coord):
        """Проверить, что BOM скачивается; иначе пропустить его."""
        try:
            self.pom(coord)
        except RepositoryError as exc:
            self.warnings.append(f"BOM skipped: {exc}")
            self.done[coord] = Effective({}, {}, [])
            return False
        return True

    def merged_properties(self, pom):
        """Свойства родителей, затем свои и встроенные (свои важнее)."""
        props = dict(self.done[pom.parent].properties) if pom.parent else {}
        props.update(pom.properties)
        props.update(project_properties(pom))
        return props

    @staticmethod
    def import_coords(pom, props):
        """BOM, импортированные в dependencyManagement (scope=import)."""
        return [(substitute(item["groupId"], props),
                 substitute(item["artifactId"], props),
                 substitute(item["version"], props))
                for item in pom.managed if item["scope"] == IMPORT_SCOPE]

    def build_effective(self, coord):
        """Собрать Effective: свойства, управление версиями, зависимости."""
        pom = self.pom(coord)
        props = self.merged_properties(pom)
        parent = self.done[pom.parent] if pom.parent else None
        managed = dict(parent.managed) if parent else {}
        for item in self.import_coords(pom, props):
            managed.update(self.done[item].managed)
        for item in pom.managed:
            if item["scope"] != IMPORT_SCOPE:
                key = (substitute(item["groupId"], props),
                       substitute(item["artifactId"], props))
                managed[key] = (substitute(item["version"], props),
                                item["scope"])
        deps = list(parent.dependencies) if parent else []
        deps.extend(pom.dependencies)
        return Effective(props, managed, deps)

    def dependencies(self, group, artifact, version):
        """Все зависимости версии пакета (включая test и optional)."""
        info = self.effective((group, artifact, version))
        result = {}
        for item in info.dependencies:
            dep = make_dependency(item, info)
            result[dep.name] = dep
        return list(result.values())

    def direct_dependencies(self, group, artifact, version):
        """Прямые зависимости, нужные для работы пакета."""
        return [dep for dep in self.dependencies(group, artifact, version)
                if dep.is_used()]


def make_dependency(item, info):
    """Зависимость с подставленными свойствами и версией из управления."""
    group = substitute(item["groupId"], info.properties)
    artifact = substitute(item["artifactId"], info.properties)
    managed_version, managed_scope = info.managed.get((group, artifact),
                                                      ("", ""))
    version = substitute(item["version"], info.properties) or managed_version
    scope = item["scope"] or managed_scope or DEFAULT_SCOPE
    return Dependency(group, artifact, pick_version(version), scope,
                      item["optional"] == "true")

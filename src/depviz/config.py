"""Чтение и проверка конфигурационного файла формата YAML."""
import os
import re
from dataclasses import dataclass

from depviz.errors import ConfigError
from depviz.yamlconf import read_yaml

KEYS = ("package", "repository", "test_mode", "version", "max_depth")
MIN_DEPTH = 1
PACKAGE_NAME = re.compile(r"^[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+$")
TEST_NAME = re.compile(r"^[A-Z]+$")
VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
URL = re.compile(r"^https?://[^\s/]+\S*$")
TRUE_WORDS = ("true", "yes", "on")
FALSE_WORDS = ("false", "no", "off")


@dataclass
class Config:
    """Параметры, настраиваемые пользователем."""

    package: str
    repository: str
    test_mode: bool
    version: str
    max_depth: int

    def items(self):
        """Вернуть пары (ключ, значение) в порядке объявления."""
        return [(key, getattr(self, key)) for key in KEYS]


def read_values(path):
    """Прочитать YAML и проверить набор ключей; вернуть словарь строк."""
    data = read_yaml(path)
    unknown = sorted(set(data) - set(KEYS))
    if unknown:
        raise ConfigError(f"unknown parameter: {unknown[0]}")
    for key in KEYS:
        if not data.get(key, ""):
            raise ConfigError(f"missing parameter: {key}")
    return {key: data[key] for key in KEYS}


def parse_bool(value):
    """Преобразовать test_mode в True или False."""
    word = value.lower()
    if word in TRUE_WORDS:
        return True
    if word in FALSE_WORDS:
        return False
    raise ConfigError(f"test_mode: expected true or false, got '{value}'")


def parse_depth(value):
    """Преобразовать max_depth в целое число не меньше MIN_DEPTH."""
    try:
        depth = int(value)
    except ValueError:
        raise ConfigError(
            f"max_depth: expected integer, got '{value}'") from None
    if depth < MIN_DEPTH:
        raise ConfigError(f"max_depth: must be >= {MIN_DEPTH}, got {depth}")
    return depth


def check_package(name, test_mode):
    """Проверить имя: groupId:artifactId или (тест) большие буквы."""
    pattern = TEST_NAME if test_mode else PACKAGE_NAME
    if not pattern.match(name):
        rule = "capital latin letters" if test_mode else \
            "groupId:artifactId"
        raise ConfigError(f"package: invalid name '{name}' ({rule})")
    return name


def check_repository(value, test_mode, base_dir):
    """Проверить URL репозитория или путь к файлу тестового репозитория."""
    if not test_mode:
        if not URL.match(value):
            raise ConfigError(
                f"repository: expected http(s) URL, got '{value}'")
        return value.rstrip("/")
    path = os.path.normpath(os.path.join(base_dir, value))
    if not os.path.isfile(path):
        raise ConfigError(f"repository: test file not found: {value}")
    return path


def check_version(value):
    """Проверить версию Maven (например, 2.17.2, 31.1-jre)."""
    if not VERSION.match(value):
        raise ConfigError(f"version: invalid version '{value}'")
    return value


def load_config(path):
    """Прочитать файл, проверить все параметры и вернуть Config."""
    raw = read_values(path)
    test_mode = parse_bool(raw["test_mode"])
    base_dir = os.path.dirname(os.path.abspath(path))
    return Config(
        package=check_package(raw["package"], test_mode),
        repository=check_repository(raw["repository"], test_mode, base_dir),
        test_mode=test_mode,
        version=check_version(raw["version"]),
        max_depth=parse_depth(raw["max_depth"]),
    )

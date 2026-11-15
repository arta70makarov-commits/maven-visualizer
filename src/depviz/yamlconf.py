"""Чтение простого YAML-файла: плоский словарь «ключ: значение».

В стандартной библиотеке Python нет модуля для YAML, а сторонние
библиотеки не используются, поэтому здесь разбирается нужное
подмножество YAML: строки «ключ: значение», комментарии #,
значения в одинарных или двойных кавычках, разделитель документа ---.
"""
import re

from depviz.errors import ConfigError

KEY_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")
QUOTES = ("'", '"')
DOCUMENT_START = "---"
COMMENT = "#"
MIN_QUOTED = 2


def strip_comment(line):
    """Убрать комментарий #, если он не внутри кавычек."""
    quote = None
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in QUOTES:
            quote = char
        elif char == COMMENT and (index == 0 or line[index - 1] in " \t"):
            return line[:index]
    return line


def unquote(value):
    """Снять кавычки вокруг значения: 'abc' или "abc" -> abc."""
    if len(value) >= MIN_QUOTED and value[0] in QUOTES \
            and value[-1] == value[0]:
        return value[1:-1]
    return value


def parse_yaml(text):
    """Разобрать текст YAML в словарь строк (с проверкой формата)."""
    result = {}
    for number, raw in enumerate(text.splitlines(), start=1):
        line = strip_comment(raw).rstrip()
        if not line.strip() or line.strip() == DOCUMENT_START:
            continue
        if line[0] in " \t":
            raise ConfigError(
                f"YAML line {number}: nested values are not supported")
        match = KEY_LINE.match(line)
        if not match:
            raise ConfigError(f"YAML line {number}: expected 'key: value'")
        key, value = match.groups()
        if key in result:
            raise ConfigError(f"YAML line {number}: duplicate key '{key}'")
        result[key] = unquote(value.strip())
    return result


def read_yaml(path):
    """Прочитать YAML-файл и вернуть словарь."""
    try:
        with open(path, encoding="utf-8") as file:
            return parse_yaml(file.read())
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"cannot read config file: {exc}") from None

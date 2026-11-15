"""Точка входа: python -m depviz [путь к config.yaml]."""
import argparse
import sys

from depviz.config import load_config
from depviz.errors import DepVizError
from depviz.maven import MavenRepository

DEFAULT_CONFIG = "config.yaml"


def parse_args(argv):
    """Разобрать аргументы командной строки."""
    parser = argparse.ArgumentParser(
        prog="depviz",
        description="Визуализация графа зависимостей пакетов Maven")
    parser.add_argument("config", nargs="?", default=DEFAULT_CONFIG,
                        help="путь к конфигурационному файлу YAML")
    return parser.parse_args(argv)


def describe(dep):
    """Строка для вывода одной зависимости."""
    version = dep.version or "(version not found)"
    return f"  {dep.name}:{version} [{dep.scope}]"


def print_direct(config, repository):
    """Вывести прямые зависимости пакета заданной версии."""
    group, artifact = config.package.split(":")
    deps = repository.dependencies(group, artifact, config.version)
    used = [dep for dep in deps if dep.is_used()]
    print(f"{config.package}:{config.version}: "
          f"direct dependencies ({len(used)})")
    for dep in used:
        print(describe(dep))
    skipped = len(deps) - len(used)
    if skipped:
        print(f"skipped test/provided/optional dependencies: {skipped}")


def run(config):
    """Выполнить работу приложения согласно конфигурации."""
    if config.test_mode:
        raise DepVizError("test repository mode is not implemented yet")
    repository = MavenRepository(config.repository)
    print_direct(config, repository)
    for warning in repository.warnings:
        print(f"warning: {warning}", file=sys.stderr)


def main(argv=None):
    """Загрузить конфигурацию и запустить приложение; вернуть код выхода."""
    args = parse_args(argv)
    try:
        config = load_config(args.config)
        run(config)
    except DepVizError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

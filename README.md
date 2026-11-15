# depviz — визуализация графа зависимостей Maven

Практическая работа №2 по дисциплине «Конфигурационное управление», вариант 20.

## Общее описание

`depviz` — консольное приложение (CLI) на Python 3, которое строит граф
зависимостей пакета менеджера пакетов Maven (Java). Используется только
стандартная библиотека Python: готовые менеджеры пакетов и библиотеки для
получения зависимостей (и для чтения YAML) не используются.

Текущий этап: **2 — сбор данных**.

## Откуда берутся зависимости

Источник — репозиторий Maven (по умолчанию Maven Central
`https://repo1.maven.org/maven2`). Каждая версия пакета описана XML-файлом
POM по адресу `{repository}/{groupId с / вместо .}/{artifactId}/{version}/
{artifactId}-{version}.pom`. Файл скачивается модулем `urllib`, XML
разбирается модулем `xml.etree.ElementTree`.

Чтобы узнать версии зависимостей, программа, как и Maven, учитывает:

- **родительские POM** (`<parent>`): свойства, `dependencyManagement`
  и зависимости наследуются;
- **свойства** `${...}`, в том числе встроенные `${project.version}`;
- **dependencyManagement** — версия берётся оттуда, если в зависимости
  её нет; **BOM** (`scope=import`) тоже учитываются;
- диапазон версий `[1.0,2.0)` — берётся нижняя граница.

Цепочка родителей и BOM обходится на явном стеке (без рекурсии).
Прямыми зависимостями считаются `compile` и `runtime`; `test`, `provided`,
`system` и `optional` пропускаются (их число выводится отдельно).

## Настройки (файл YAML)

| Параметр | Описание | Пример |
|---|---|---|
| `package` | имя пакета `groupId:artifactId` | `junit:junit` |
| `repository` | URL репозитория или путь к файлу тестового репозитория | `https://repo1.maven.org/maven2` |
| `test_mode` | режим работы с тестовым репозиторием (`true` / `false`) | `false` |
| `version` | версия пакета | `4.13.2` |
| `max_depth` | максимальная глубина анализа (целое ≥ 1) | `3` |

```yaml
# configs/junit.yaml
package: junit:junit
repository: https://repo1.maven.org/maven2
test_mode: false
version: 4.13.2
max_depth: 3
```

YAML читается собственным модулем `yamlconf.py` (в стандартной библиотеке
Python нет модуля для YAML): строки `ключ: значение`, комментарии `#`,
значения в кавычках, разделитель `---`.

### Обработка ошибок

При ошибке выводится `error: ...` и код выхода 1:

- нет файла; строка не в формате `ключ: значение`; вложенные значения;
  повтор ключа;
- неизвестный, пропущенный или пустой параметр;
- имя пакета не `groupId:artifactId` (в тестовом режиме — только `A-Z`);
- `repository` не URL или файл тестового репозитория не найден;
- `test_mode` не `true`/`false`;
- недопустимые символы в версии;
- `max_depth` не число или меньше 1;
- пакета или версии нет в репозитории, испорченный POM, репозиторий
  недоступен.

## Функции

| Модуль | Функция | Назначение |
|---|---|---|
| `yamlconf.py` | `read_yaml`, `parse_yaml` | прочитать и разобрать YAML |
| `yamlconf.py` | `strip_comment`, `unquote` | убрать комментарий и кавычки |
| `config.py` | `load_config`, `read_values` | прочитать и проверить параметры |
| `config.py` | `parse_bool`, `parse_depth`, `check_package`, `check_repository`, `check_version` | проверки |
| `maven.py` | `pom_url`, `download` | адрес POM и скачивание (`urllib`) |
| `maven.py` | `parse_pom` | разобрать XML файла POM |
| `maven.py` | `MavenRepository.effective` | POM с родителями и BOM (стек) |
| `maven.py` | `MavenRepository.direct_dependencies` | прямые зависимости версии |
| `maven.py` | `substitute`, `pick_version` | свойства `${...}`, диапазоны версий |
| `__main__.py` | `print_direct` | вывести прямые зависимости |
| `__main__.py` | `main` | точка входа, ошибки и код выхода |

## Запуск

Нужен только Python 3.8+.

```sh
./run.sh configs/junit.yaml
./tests/sh/stage1.sh
./tests/sh/stage2.sh
PYTHONPATH=src python3 -m unittest discover -s tests -t .
```

## Пример

```
$ ./run.sh configs/jackson.yaml
com.fasterxml.jackson.core:jackson-databind:2.17.2: direct dependencies (2)
  com.fasterxml.jackson.core:jackson-annotations:2.17.2 [compile]
  com.fasterxml.jackson.core:jackson-core:2.17.2 [compile]
skipped test/provided/optional dependencies: 10
```

# depviz — визуализация графа зависимостей Maven

Практическая работа №2 по дисциплине «Конфигурационное управление», вариант 20.

## Общее описание

`depviz` — консольное приложение (CLI) на Python 3, которое строит граф
зависимостей пакета менеджера пакетов Maven (Java). Используется только
стандартная библиотека Python: готовые менеджеры пакетов и библиотеки для
получения зависимостей (и для чтения YAML) не используются.

Текущий этап: **4 — дополнительные операции** (обратные зависимости).

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

## Построение графа

Граф строится обходом в ширину (BFS) без рекурсии (`graph.build_graph`):
очередь `collections.deque`, словарь глубин служит множеством посещённых
вершин. Каждая вершина раскрывается один раз, поэтому циклические
зависимости не приводят к зацикливанию. Вершины на глубине `max_depth`
не раскрываются (`... (max depth reached)`). Вершина графа —
`groupId:artifactId:version`.

Циклы ищутся обходом в глубину на явном стеке (`graph.find_cycles`):
ребро в вершину, которая сейчас лежит на пути от корня, замыкает цикл.

Если POM зависимости не найден или версия не определилась, программа
выводит предупреждение `warning: ...` и продолжает обход.

### Тестовый режим

При `test_mode: true` в `repository` указывается путь к файлу описания
графа. Пакеты называются большими латинскими буквами, формат строки —
`ПАКЕТ: ЗАВИСИМОСТИ`, `#` — комментарий:

```
# tests/repos/cycle.txt
A: B
B: C
C: A D
D:
```

| Файл | Случай |
|---|---|
| `simple.txt` | общая зависимость (D нужна и B, и C) |
| `chain.txt` | длинная цепочка — проверка `max_depth` |
| `cycle.txt` | цикл A → B → C → A |
| `self.txt` | пакет зависит сам от себя |
| `complex.txt` | два цикла и неописанный лист K |
| `bad_format.txt`, `bad_name.txt` | ошибки формата |

## Обратные зависимости

При `mode: reverse` выводятся пакеты, которые зависят от заданного
(напрямую и транзитивно). Используется тот же BFS (`build_graph`), но
вместо функции «зависимости пакета» ему передаётся функция «кто зависит
от пакета» (`FileSource.reverse_source`), построенная разворотом всех
рёбер тестового репозитория (`graph.reverse_edges`). Ограничение
`max_depth` и обработка циклов работают так же.

Режим поддерживается для тестового репозитория: POM хранит только прямые
зависимости пакета, и чтобы найти обратные, пришлось бы скачать весь
Maven Central.

## Настройки (файл YAML)

| Параметр | Описание | Пример |
|---|---|---|
| `package` | имя пакета `groupId:artifactId` | `junit:junit` |
| `repository` | URL репозитория или путь к файлу тестового репозитория | `https://repo1.maven.org/maven2` |
| `test_mode` | режим работы с тестовым репозиторием (`true` / `false`) | `false` |
| `version` | версия пакета | `4.13.2` |
| `max_depth` | максимальная глубина анализа (целое ≥ 1) | `3` |
| `mode` | необязательный: `graph` (по умолчанию) или `reverse` | `reverse` |

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
  недоступен;
- ошибка формата файла тестового репозитория (с номером строки),
  корневого пакета нет в тестовом репозитории;
- неизвестный `mode`, `mode: reverse` без тестового репозитория.

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
| `sources.py` | `FileSource` | тестовый репозиторий из файла |
| `sources.py` | `MavenSource` | репозиторий Maven: вершина (имя, версия) |
| `sources.py` | `make_source` | выбрать источник по `test_mode` |
| `graph.py` | `build_graph` | BFS без рекурсии с ограничением глубины |
| `graph.py` | `find_cycles` | найти циклы |
| `graph.py` | `reverse_edges` | развернуть рёбра графа |
| `sources.py` | `FileSource.reverse_source` | «кто зависит от пакета» |
| `__main__.py` | `print_reverse` | вывести обратные зависимости |
| `__main__.py` | `print_graph`, `print_cycles` | вывести граф и циклы |
| `__main__.py` | `main` | точка входа, ошибки и код выхода |

## Запуск

Нужен только Python 3.8+.

```sh
./run.sh configs/junit.yaml
./tests/sh/stage1.sh
./tests/sh/stage2.sh
./tests/sh/stage3.sh
./tests/sh/stage4.sh
PYTHONPATH=src python3 -m unittest discover -s tests -t .
```

## Примеры

```
$ ./run.sh configs/test_cycle.yaml
dependency graph of A (max_depth = 10)
packages: 4, edges: 4
  [0] A -> B
  [1] B -> C
  [2] C -> A, D
  [3] D
cycles: 1
  A -> B -> C -> A

$ ./run.sh configs/reverse_simple_d.yaml
reverse dependencies of D (max_depth = 10)
packages: 4, edges: 4
  [0] D <- B, C
  [1] B <- A
  [1] C <- A
  [2] A
packages depending on D: B, C, A
cycles: none

$ ./run.sh configs/junit.yaml
dependency graph of junit:junit:4.13.2 (max_depth = 3)
packages: 2, edges: 1
  [0] junit:junit:4.13.2 -> org.hamcrest:hamcrest-core:1.3
  [1] org.hamcrest:hamcrest-core:1.3
cycles: none
```

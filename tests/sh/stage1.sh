#!/bin/sh
# Этап 1: вывод параметров из YAML и обработка ошибок всех параметров.
cd "$(dirname "$0")/../.." || exit 1
show() {
    echo "=== $1"
    ./run.sh "$1"
    echo "(код выхода $?)"
    echo
}
show configs/jackson.yaml
show configs/test_simple.yaml
show tests/configs/nope.yaml
for f in tests/configs/*.yaml; do
    show "$f"
done

#!/bin/sh
# Этап 2: прямые зависимости заданной версии пакета из Maven Central.
cd "$(dirname "$0")/../.." || exit 1
show() {
    echo "=== $1"
    ./run.sh "$1"
    echo "(код выхода $?)"
    echo
}
show configs/junit.yaml
show configs/commons_text.yaml
show configs/jackson.yaml
show tests/configs/unknown_package.yaml
show tests/configs/unknown_version.yaml
show tests/configs/bad_host.yaml

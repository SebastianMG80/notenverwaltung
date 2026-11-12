#!/usr/bin/env bash
# Startet die Notenverwaltung aus dem Quellcode (Linux).
# Erwartet die Python-Umgebung unter ~/.venvs/notenverwaltung (siehe README.md).
set -euo pipefail
cd "$(dirname "$0")"
PY="${NOTENVERWALTUNG_PYTHON:-$HOME/.venvs/notenverwaltung/bin/python}"
PYTHONPATH=src exec "$PY" -m notenverwaltung "$@"

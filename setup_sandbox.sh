#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
python3 -m venv "$ROOT/sandbox/.venv"
"$ROOT/sandbox/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/sandbox/.venv/bin/python" -m pip install -r "$ROOT/sandbox/requirements.txt"
echo "Sandbox ready: $ROOT/sandbox/.venv/bin/python"

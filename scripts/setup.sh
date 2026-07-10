#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
if [[ "$(.venv/bin/python -c 'import sys; print(sys.prefix)')" != "$PWD/.venv" ]]; then
  echo "Refusing to install outside the project .venv" >&2
  exit 1
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[test]'
echo "SceneChat development environment is ready."


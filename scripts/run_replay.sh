#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -x .venv/bin/python ]] || { echo "Run scripts/setup.sh first." >&2; exit 1; }
SCENECHAT_MODE=replay VISION_PROVIDER=replay DETECTOR_BACKEND=replay exec .venv/bin/python -m scenechat


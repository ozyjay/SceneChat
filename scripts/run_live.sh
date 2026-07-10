#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -x .venv/bin/python ]] || { echo "Run scripts/setup.sh and install camera extras first." >&2; exit 1; }
SCENECHAT_MODE=live DETECTOR_BACKEND="${DETECTOR_BACKEND:-yolo}" VISION_PROVIDER="${VISION_PROVIDER:-vllm}" exec .venv/bin/python -m scenechat


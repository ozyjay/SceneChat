#!/usr/bin/env bash
set -euo pipefail
pid="$(pgrep -f '[p]ython -m scenechat' || true)"
if [[ -z "$pid" ]]; then echo "SceneChat is not running."; exit 0; fi
kill -TERM $pid
echo "Requested graceful shutdown for PID(s): $pid"


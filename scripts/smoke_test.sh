#!/usr/bin/env bash
set -euo pipefail
base="${SCENECHAT_URL:-http://127.0.0.1:8900}"
curl --fail --silent --show-error "$base/api/health" | python3 -m json.tool
curl --fail --silent --show-error "$base/api/config" >/dev/null
curl --fail --silent --show-error "$base/" >/dev/null
echo "SceneChat smoke test passed."

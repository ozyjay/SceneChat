#!/usr/bin/env bash
set -euo pipefail
failed=0
for port in 3900 8900; do
  if ss -ltn "sport = :$port" 2>/dev/null | tail -n +2 | grep -q .; then
    echo "Port $port is already in use." >&2
    failed=1
  else
    echo "Port $port is available."
  fi
done
exit "$failed"


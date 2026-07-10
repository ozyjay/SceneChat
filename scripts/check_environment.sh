#!/usr/bin/env bash
set -u
echo "SceneChat environment check"
echo "==========================="
grep '^PRETTY_NAME=' /etc/os-release 2>/dev/null || true
python3 --version 2>&1
docker --version 2>&1 || true
podman --version 2>&1 || true
lspci 2>/dev/null | grep -Ei 'vga|3d|display' | head -1 || true
free -h 2>/dev/null | head -2 || true
echo "Video devices:"
find /dev -maxdepth 1 -name 'video*' -print 2>/dev/null || true
echo "ROCm:"
rocminfo 2>&1 | head -20 || true
echo "Relevant listeners:"
ss -ltn 2>/dev/null | grep -E ':(3900|8900|8000)\b' || echo "none"


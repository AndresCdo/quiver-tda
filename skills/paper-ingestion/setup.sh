#!/usr/bin/env bash
# Thin wrapper around the cross-platform micromamba provisioner.
# The real logic (OS + hardware detection, package install, env cleanup) lives in
# scripts/setup_env.py so Linux, macOS, and Windows share one source of truth.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "[!!] $PYTHON not found. Install Python 3.10+ and re-run." >&2
  exit 1
fi

exec "$PYTHON" "$ROOT/scripts/setup_env.py" install "$@"

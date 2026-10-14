#!/usr/bin/env bash
# THUNDER AI launcher (macOS / Linux)
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  exec python3 scripts/launcher.py start "$@"
fi
echo "Python 3.11 or newer is needed. Download it from https://www.python.org/downloads/"
read -r -p "Press Enter to close..."

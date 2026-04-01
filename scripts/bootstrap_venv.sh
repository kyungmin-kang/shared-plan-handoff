#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m venv .venv
./.venv/bin/python setup.py develop

cat <<'EOF'

Project environment is ready.

Use the bridge with:
  source .venv/bin/activate
  pm --help

Or without activating:
  ./.venv/bin/pm --help

Before running `pm bootstrap`, export:
  NOTION_API_TOKEN
  NOTION_PARENT_PAGE_ID

Optional later, if you want newer packaging tools and have network access:
  ./.venv/bin/python -m pip install --upgrade pip setuptools wheel

EOF

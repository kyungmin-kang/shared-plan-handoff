#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

choose_python() {
  local candidates=()

  if [[ -n "${SHARED_PLAN_HANDOFF_PYTHON:-}" ]]; then
    candidates+=("${SHARED_PLAN_HANDOFF_PYTHON}")
  fi

  candidates+=(python3.13 python3.12 python3.11 python3)

  for candidate in "${candidates[@]}"; do
    if ! command -v "$candidate" >/dev/null 2>&1; then
      continue
    fi

    if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
    then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  cat >&2 <<'EOF'
Shared Plan Handoff requires Python 3.11+.

Install Python 3.11 or newer, or rerun with:
  SHARED_PLAN_HANDOFF_PYTHON=/path/to/python3.11 ./scripts/bootstrap_venv.sh
EOF
  return 1
}

PYTHON_BIN="$(choose_python)"

"$PYTHON_BIN" -m venv .venv

if ! ./.venv/bin/python -m pip install -e .; then
  echo "Editable install via pip failed; falling back to setup.py develop." >&2
  ./.venv/bin/python setup.py develop
fi

if [[ ! -x ./.venv/bin/pm ]]; then
  cat >&2 <<'EOF'
Bootstrap completed without creating the pm executable.

Try:
  ./.venv/bin/python -m notion_pm_bridge.cli --help

If that works, please report the packaging environment so the installer can be improved.
EOF
  exit 1
fi

cat <<'EOF'

Project environment is ready.

Use the bridge with:
  source .venv/bin/activate
  pm --help

Or without activating:
  ./.venv/bin/pm --help

The bootstrap auto-selects Python 3.11+.
Override it if needed with:
  SHARED_PLAN_HANDOFF_PYTHON=/path/to/python3.11 ./scripts/bootstrap_venv.sh

For chat-first use with Notion MCP, no REST token is required.

If you want REST fallback later, export:
  NOTION_API_TOKEN
  NOTION_PARENT_PAGE_ID

Optional later, if you want newer packaging tools and have network access:
  ./.venv/bin/python -m pip install --upgrade pip setuptools wheel

EOF

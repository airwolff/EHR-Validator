#!/usr/bin/env bash
# pre-commit-gate.sh — block a commit/push if the test suite is red or a secret is staged.
#
# The project rule is "verify by running, not asserting." This makes that mechanical:
# nothing can commit a change that reds the temp-71.2°F regression guard.
set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Only fire on commit or push.
if ! echo "$COMMAND" | grep -qE 'git[[:space:]]+(commit|push)'; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

# --- Guard 1: no secret may enter the history. ---------------------------------
# The Lyzr key was exposed once already and rotated. Match assigned *values*, not
# bare env-var names — os.environ["LYZR_API_KEY"] is correct code and must pass.
SECRET_RE='sk-[A-Za-z0-9]{16,}|(api[_-]?key|apikey|secret|token|password)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"'][A-Za-z0-9_\-]{16,}["'"'"']'
if git diff --cached | grep -qEi "^\+.*($SECRET_RE)"; then
  echo "BLOCKED: a staged line looks like a hardcoded secret." >&2
  echo "Offending lines (values redacted below — inspect with: git diff --cached):" >&2
  git diff --cached | grep -nEi "^\+.*($SECRET_RE)" | cut -c1-60 | sed 's/^/  /' >&2
  echo "Secrets belong in .env (gitignored) only. Unstage the file and use os.environ." >&2
  exit 2
fi

if git diff --cached --name-only | grep -qE '(^|/)\.env$'; then
  echo "BLOCKED: .env is staged. It must never be committed (holds the Lyzr key)." >&2
  echo "Run: git restore --staged .env" >&2
  exit 2
fi

# --- Guard 2: the test suite must be green. ------------------------------------
if [[ ! -d tests ]]; then
  exit 0   # no suite yet — nothing to gate
fi

PY=$(command -v python || command -v python3)
if ! "$PY" -m pytest -q > /tmp/ehr-pytest.log 2>&1; then
  echo "BLOCKED: pytest is red — refusing to commit." >&2
  echo "" >&2
  tail -15 /tmp/ehr-pytest.log | sed 's/^/  /' >&2
  echo "" >&2
  echo "Full log: /tmp/ehr-pytest.log" >&2
  echo "Fix the tests, or if the behavior change is intentional, update the test" >&2
  echo "and say so explicitly — do not weaken the temp-71.2 guard to get green." >&2
  exit 2
fi

exit 0

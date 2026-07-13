#!/usr/bin/env bash
# protect-invariants.sh — PreToolUse (Write|Edit) guard for this repo's written-down rules.
#
# Two invariants live in docs/session-protocol.md and CLAUDE.md but nothing enforced them:
#   1. docs/decisions.md is APPEND-ONLY (a reversal is a new entry that supersedes, never a rewrite).
#   2. db/queries.sql stays UPPERCASE and unformatted.
# It also refuses to write a secret into any file.
set -euo pipefail

INPUT=$(cat)

# Bail out loudly-but-safely on a payload we can't parse. Without this, `set -e` would
# kill the script on jq's error with a non-2 exit, which Claude Code treats as a soft
# error and runs the tool anyway — i.e. the guard would silently stop guarding.
if ! printf '%s' "$INPUT" | jq -e . > /dev/null 2>&1; then
  echo "protect-invariants.sh: could not parse the hook payload; not enforcing." >&2
  exit 0
fi

TOOL=$(printf '%s' "$INPUT" | jq -r '.tool_name // empty')
FILE_PATH=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')

[[ -z "$FILE_PATH" ]] && exit 0

REL_PATH="${FILE_PATH#${CLAUDE_PROJECT_DIR:-}/}"

# --- Never write a live secret into a file. -----------------------------------
NEW_CONTENT=$(printf '%s' "$INPUT" | jq -r '(.tool_input.content // .tool_input.new_string) // empty')
if printf '%s' "$NEW_CONTENT" | grep -qE 'sk-[A-Za-z0-9]{16,}'; then
  echo "BLOCKED: that content contains something shaped like a live API key." >&2
  echo "Secrets go in .env (gitignored) and are read via os.environ." >&2
  exit 2
fi

# --- docs/decisions.md is append-only. ----------------------------------------
if [[ "$REL_PATH" == "docs/decisions.md" ]]; then
  if [[ "$TOOL" == "Write" ]]; then
    echo "BLOCKED: docs/decisions.md is append-only — Write would overwrite the whole log." >&2
    echo "Use Edit to append a new dated entry at the end instead." >&2
    exit 2
  fi
  # An Edit is append-only iff the old text survives verbatim inside the new text.
  # Appending keeps old_string intact and adds after it; rewriting or deleting does not.
  if ! printf '%s' "$INPUT" | jq -e '
        (.tool_input.new_string // "") as $new
      | (.tool_input.old_string // "") as $old
      | ($old | length) > 0 and ($new | contains($old))' > /dev/null; then
    echo "BLOCKED: that edit to docs/decisions.md removes or rewrites existing text." >&2
    echo "The log is append-only (docs/session-protocol.md). To reverse a decision, append a" >&2
    echo "new entry whose Status supersedes the old one by name — never edit the old entry." >&2
    exit 2
  fi
fi

# --- db/queries.sql: keep SQL uppercase, never autoformat. ---------------------
if [[ "$REL_PATH" == "db/queries.sql" ]] && [[ -n "$NEW_CONTENT" ]]; then
  if printf '%s' "$NEW_CONTENT" | grep -qE '^[[:space:]]*(select|from|where|group by|order by|join|with|insert|update|create)[[:space:]]'; then
    echo "BLOCKED: db/queries.sql keeps SQL keywords UPPERCASE (CLAUDE.md)." >&2
    echo "Found a lowercase keyword at the start of a line. Use SELECT / FROM / WHERE ..." >&2
    exit 2
  fi
fi

exit 0

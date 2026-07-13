#!/usr/bin/env bash
# session-start-staleness.sh — run the start-of-session staleness check automatically.
#
# docs/session-protocol.md says a handoff is "a claim, not proof" and must be verified
# against git before it's trusted. That check only ran when someone remembered to run it —
# and the 2026-07-11 handoff did go stale. This makes it fire on every session start.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}" 2>/dev/null || exit 0
git rev-parse --git-dir > /dev/null 2>&1 || exit 0

HANDOFF="docs/handoff.md"
ACTUAL_HEAD=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

echo "## Start-of-session staleness check (auto-run by hook)"
echo ""
echo "Actual HEAD: \`$ACTUAL_HEAD\`  ·  branch: \`$(git branch --show-current)\`"

if [[ -f "$HANDOFF" ]]; then
  # The handoff records the HEAD it was written against, as a short sha in backticks.
  CLAIMED_HEAD=$(grep -oE 'HEAD at write time:.*`[0-9a-f]{7,40}`' "$HANDOFF" 2>/dev/null \
                 | grep -oE '[0-9a-f]{7,40}' | head -1 || true)

  if [[ -z "$CLAIMED_HEAD" ]]; then
    echo "Handoff: present, but states no HEAD — treat it as unverified."
  elif [[ "$ACTUAL_HEAD" == "$CLAIMED_HEAD"* ]] || [[ "$CLAIMED_HEAD" == "$ACTUAL_HEAD"* ]]; then
    echo "Handoff: **fresh** — its HEAD (\`$CLAIMED_HEAD\`) matches the repo."
  else
    echo "Handoff: **STALE** — it claims HEAD \`$CLAIMED_HEAD\`, repo is at \`$ACTUAL_HEAD\`."
    echo ""
    echo "Commits since the handoff was written:"
    git log --oneline "$CLAIMED_HEAD..HEAD" 2>/dev/null | sed 's/^/  - /' || echo "  (cannot diff — unknown sha)"
    echo ""
    echo "Per docs/session-protocol.md: trust git and the code over the prose."
    echo "Re-verify each claim before acting on it, and rewrite the handoff early."
  fi
else
  echo "Handoff: none at $HANDOFF."
fi

echo ""
DIRTY=$(git status -s)
if [[ -n "$DIRTY" ]]; then
  echo "Uncommitted changes:"
  echo "$DIRTY" | sed 's/^/  /'
else
  echo "Working tree: clean."
fi

exit 0

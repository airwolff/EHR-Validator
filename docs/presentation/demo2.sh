#!/usr/bin/env bash
# demo2.sh — Slide 4, the same test five times. Run SETUP first (any time after).
set -euo pipefail
cd "$(dirname "$0")/../.."
pause(){ printf '\n'; read -r -p "   ── press Enter ──"; printf '\n\n'; }

echo "### 1 of 2 — both engines, 5 records, 5 runs, temperature 0, only the order changed"
python -m app.agents.compare --runs 5 --mode replay
echo ">>> caught: 14, 14, 15, 14, 12   false alarms: 0, 0, 7, 4, 0   — same records, different answers."
pause

echo "### 2 of 2 — the same scorecard, as SQL over the saved results (not my summary)"
sqlite3 -header -column ehr_triage.db "
SELECT cr.run_number, cr.mode,
  SUM(res.outcome='caught')            AS caught,
  SUM(res.outcome='severity_mismatch') AS misgraded,
  SUM(res.outcome='missed')            AS missed,
  SUM(res.outcome='false_alarm')       AS false_alarms
FROM comparison_runs cr
LEFT JOIN comparison_results res ON res.comparison_run_id = cr.comparison_run_id
GROUP BY cr.comparison_run_id ORDER BY cr.run_number;"
echo ">>> the rules: 15/15 every run. The AI: a different answer every time the order changed."

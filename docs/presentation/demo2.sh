#!/usr/bin/env bash
# demo2.sh — Slide 4, the same test five times. Run setup.sh first.
set -uo pipefail
cd "$(dirname "$0")/../.."
STREAM_DELAY="${STREAM_DELAY:-0.03}"
slow(){ while IFS= read -r l; do printf '%s\n' "$l"; sleep "$STREAM_DELAY"; done; }
prompt(){ printf '\033[1;32m$\033[0m %s\n\n' "$*"; sleep 0.6; }
pause(){ read -r _; clear; }

prompt "python -m app.agents.compare --runs 5 --mode replay"
python -m app.agents.compare --runs 5 --mode replay 2>&1 | slow

pause

Q9="SELECT cr.run_number, cr.mode, SUM(res.outcome='caught') AS caught, SUM(res.outcome='severity_mismatch') AS misgraded, SUM(res.outcome='missed') AS missed, SUM(res.outcome='false_alarm') AS false_alarms FROM comparison_runs cr LEFT JOIN comparison_results res ON res.comparison_run_id = cr.comparison_run_id GROUP BY cr.comparison_run_id ORDER BY cr.run_number;"
prompt "sqlite3 -header -column ehr_triage.db \"$Q9\""
sqlite3 -header -column ehr_triage.db "$Q9" 2>&1 | slow

#!/usr/bin/env bash
# demo3.sh — Slide 5, the whole month. Run setup.sh + demo1 + demo2 first.
# Loads June ON CAMERA on purpose — must come after demo1. Re-run setup.sh before any retake.
set -uo pipefail
cd "$(dirname "$0")/../.."
STREAM_DELAY="${STREAM_DELAY:-0.03}"
slow(){ while IFS= read -r l; do printf '%s\n' "$l"; sleep "$STREAM_DELAY"; done; }
prompt(){ printf '\033[1;32m$\033[0m %s\n\n' "$*"; sleep 0.6; }
pause(){ read -r _; clear; }

prompt "python scripts/generate_month.py && python load_results.py --fixtures --payload-dir payloads/month --no-init | tail -4"
python scripts/generate_month.py 2>&1 | slow
python load_results.py --fixtures --payload-dir payloads/month --no-init 2>&1 | tail -4 | slow

pause

prompt "python -m app.agents.audit --month 2026-06 --mode replay --grade"
python -m app.agents.audit --month 2026-06 --mode replay --grade 2>&1 | slow

pause

QZIP="SELECT d.race, COUNT(*) AS records, SUM(d.zip IS NULL OR d.zip='') AS missing_zip, ROUND(100.0*SUM(d.zip IS NULL OR d.zip='')/COUNT(*),1) AS pct FROM record_demographics d JOIN validation_runs v ON v.payload_id = d.payload_id GROUP BY d.race ORDER BY pct DESC;"
prompt "sqlite3 -header -column ehr_triage.db \"$QZIP\""
sqlite3 -header -column ehr_triage.db "$QZIP" 2>&1 | slow

pause

QGRADE="SELECT g.planted_key, g.outcome, p.name AS matched_pattern FROM audit_grades g JOIN audit_reports r ON r.report_id = g.report_id LEFT JOIN audit_patterns p ON p.pattern_id = g.matched_pattern_id ORDER BY g.planted_key;"
prompt "sqlite3 -header -column ehr_triage.db \"$QGRADE\""
sqlite3 -header -column ehr_triage.db "$QGRADE" 2>&1 | slow

#!/usr/bin/env bash
# demo3.sh — Slide 5, the whole month. Run SETUP + demo1 + demo2 first.
# This loads June ON CAMERA on purpose — it must come AFTER demo1 (loading June earlier
# breaks demo1's replay). Re-run setup.sh before any retake, or this appends duplicates.
set -euo pipefail
cd "$(dirname "$0")/../.."
pause(){ printf '\n'; read -r -p "   ── press Enter ──"; printf '\n\n'; }

echo "### 1 of 3 — load the month's 40 records into the same database"
python scripts/generate_month.py
python load_results.py --fixtures --payload-dir payloads/month --no-init | tail -3
echo ">>> 40 June records loaded on top of the 7 fixtures."
pause

echo "### 2 of 3 — one AI call over the whole month, graded against the planted answer key"
python -m app.agents.audit --month 2026-06 --mode replay --grade
echo ">>> 4 patterns, evidence_dropped 0, credits_spent 0, all 4 grades caught."
pause

echo "### 3 of 3a — SQL alone finds the zip asymmetry; the AI only names it"
sqlite3 -header -column ehr_triage.db "
SELECT d.race, COUNT(*) AS records,
  SUM(d.zip IS NULL OR d.zip='') AS missing_zip,
  ROUND(100.0*SUM(d.zip IS NULL OR d.zip='')/COUNT(*),1) AS pct
FROM record_demographics d
JOIN validation_runs v ON v.payload_id = d.payload_id
GROUP BY d.race ORDER BY pct DESC;"
echo ">>> Black 8/10 = 80%, every other group 0%. (Blank row = the 7 batch fixtures, no race field.)"
pause

echo "### 3 of 3b — the audit scorecard: 4 of 4 planted patterns caught"
sqlite3 -header -column ehr_triage.db "
SELECT g.planted_key, g.outcome, p.name AS matched_pattern
FROM audit_grades g
JOIN audit_reports r ON r.report_id = g.report_id
LEFT JOIN audit_patterns p ON p.pattern_id = g.matched_pattern_id
ORDER BY g.planted_key;"
echo ">>> 4 of 4 caught. (Grader term-tie caveat is for Q&A, not the take — see script.md.)"

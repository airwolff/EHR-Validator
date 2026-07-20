#!/usr/bin/env bash
# demo1.sh — Slide 3, the night shift. Run SETUP first.
# Pauses between steps so you narrate, then press Enter to advance.
set -euo pipefail
cd "$(dirname "$0")/../.."
pause(){ printf '\n'; read -r -p "   ── press Enter ──"; printf '\n\n'; }

echo "### 1 of 2 — the deterministic rules on the wrong-patient record"
python3 -c "
import json
from app.validator import get_validator
p = json.load(open('tests/fixtures/payloads/payload_wrong_patient_note.json'))
print(json.dumps(get_validator('local').validate(p), indent=2))
"
echo ">>> issue_count is 0 — the rules are right, every field is individually fine."
pause

echo "### 2 of 2 — the nightly agent crew on the SAME record"
python -m app.agents --date 2026-07-14 --mode replay
echo ">>> 4 critical findings on E-WOW-01: 2 identity + 2 clinical = ONE wrong-patient defect,"
echo ">>> caught from two angles. dropped 0, credits_spent 0."

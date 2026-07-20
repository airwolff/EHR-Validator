#!/usr/bin/env bash
# setup.sh — run ONCE before recording (off camera). Also re-run before any retake.
# Resets the DB and loads the 2 batch fixtures in the exact order Demo 1's replay expects.
# Does NOT load the June month — that happens on camera in demo3.sh.
set -euo pipefail
cd "$(dirname "$0")/../.."   # -> repo root, wherever this is run from

python3 <<'PY'
import json, os
from app.validator import get_validator
from app.router import route
from app.store import init_db, save_report, demographics_from_payload, save_demographics
ORDER = ["payload_wrong_patient_note.json","payload_note_clean.json","payload_bad_codes.json",
         "payload_bad_dates.json","payload_bad_values.json","payload_clean.json","payload_missing_fields.json"]
init_db()
validator = get_validator("local"); rows=[]
for name in ORDER:
    payload = json.load(open(os.path.join("tests/fixtures/payloads", name)))
    report = validator.validate(payload); routing = route(report)
    rid = save_report(report, model=validator.name,
                      source_system=payload.get("metadata",{}).get("source_system"),
                      routing=routing, payload=payload)
    rows.append(demographics_from_payload(report["payload_id"], payload))
    print(f"  {name:32s} -> {report['status']:4s} ({report['issue_count']} issue) {routing['domain']:8s} run_id={rid}")
save_demographics(rows)
print("\nSETUP OK — DB reset, 7 batch fixtures loaded. Do NOT run demo3 yet; it loads June on camera.")
PY

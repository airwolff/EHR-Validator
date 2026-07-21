#!/usr/bin/env bash
# demo1.sh — Slide 3, the night shift. Run setup.sh first.
set -uo pipefail
cd "$(dirname "$0")/../.."
STREAM_DELAY="${STREAM_DELAY:-0.03}"                                   # per-line scroll speed; override with STREAM_DELAY=…
slow(){ while IFS= read -r l; do printf '%s\n' "$l"; sleep "$STREAM_DELAY"; done; }
prompt(){ printf '\033[1;32m$\033[0m %s\n\n' "$*"; sleep 0.6; }
pause(){ read -r _; clear; }

PYSNIP="import json, app.validator as V; p=json.load(open('tests/fixtures/payloads/payload_wrong_patient_note.json')); print(json.dumps(V.get_validator('local').validate(p), indent=2))"
prompt "python3 -c \"$PYSNIP\""
python3 -c "$PYSNIP" 2>&1 | slow

pause

prompt "python -m app.agents --date 2026-07-14 --mode replay"
python -m app.agents --date 2026-07-14 --mode replay 2>&1 | slow

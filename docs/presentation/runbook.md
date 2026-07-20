# Demo runbook — three replay segments, zero credits

Presenter doc for the recorded 15-minute walkthrough. Every command below was run for real
(replay mode, SQLite, local machine) and its output pasted in — nothing here is invented.
`--mode live` never appears in this doc; do not add it while recording.

Segments, in recording order:

1. Nightly agent run (the wow-record batch)
2. Five-try comparison (the thesis scorecard)
3. Month-end audit (the bias-finding grade)

---

## RECORDING FORMAT: ONE CONTINUOUS TAKE

Decided 2026-07-20. The deck lives on one macOS desktop, the terminal on another, and the
whole talk is recorded in a single pass with a three-finger swipe between them. **No editing.**

What that changes:

- **Everything below must be staged before you press record.** There is no cutting room. Run
  Step A to completion, verify its output matches, and only then start recording.
- **Steps B and C happen ON CAMERA**, between Segment 2 and Segment 3. They cannot be
  pre-staged — Segment 1 breaks if the June month is loaded first (see the order rule below).
  This is fine; narrate it as "now I load the month's 40 records." Pipe Step C through
  `| tail -4` so it doesn't spray 40 lines across the screen.
- **A fumble means a full retake.** Keep Step A on the clipboard so a restart is one paste
  away, and do a dry run of the whole sequence before the real take.
- Record the **screen area covering both desktops' content** — with `Cmd-Shift-5`, choose
  **"Record Entire Screen"**, not "Record Selected Portion". A portion selection does not
  follow a desktop swipe.

## 0. Prep (before you hit record)

- Font size **18pt or larger** — check Terminal/iTerm preferences, not just a one-off zoom.
- **Dark theme.** Light backgrounds blow out on screen recordings, and the deck is dark by
  design so the two match.
- Terminal maximized on its own desktop; `deck.html` open full-screen on the other.
- `cd` to the repo root (`/Users/andywolff/Desktop/projects/sql_portfolio/ehr-triage`) before
  you start — every command below assumes that as the working directory.
- Clear scrollback (`Cmd-K` in Terminal.app) so the recording starts clean.
- Silence notifications (Do Not Disturb) — a banner mid-take costs you the whole take.
- Run **Step A** and confirm its output. Then record.

## macOS screen recording how-to

1. `Cmd-Shift-5` opens the capture toolbar.
2. Choose **"Record Entire Screen"** (see the format note above — required for desktop swipes).
3. Click **Record**. A countdown starts, then it's live.
4. Stop from the menu-bar icon (square in a circle) or `Cmd-Shift-5` again → Stop.
5. The clip lands on the Desktop as a `.mov`.

## Still-shot fallback

Not required by the assignment — Mahima's spec asks only for the four sections in 15 minutes,
with no format or screenshot requirement. Keep these as insurance only, taken with
`Cmd-Shift-4` during the dry run, in case a take is unusable and you have to fall back to
narrating over stills:

1. **Segment 1** — the batch's `worklist` JSON array (4 critical findings on `E-WOW-01`).
2. **Segment 2** — the Q9 scorecard table in the sqlite3 shell (5 rows, one per run).
3. **Segment 3** — the Q13 grades table in the sqlite3 shell (4 rows, all `caught`).

---

## Prerequisite: reload sequence (run once, before recording)

**Known state going in:** the local `ehr_triage.db` may already hold arbitrary data from
earlier work. All three segments below need a *specific* database state, and the ORDER the
steps run in matters, not just which data ends up loaded:

- Segment 1's replay only works if the two note-bearing fixture records are loaded in a
  *specific order* (the recorded Lyzr transcripts are keyed by an exact-message hash, and
  the hash depends on which records are in the batch and the order they were inserted —
  see `app/agents/specialists.py:build_message`).
- **Segment 1 must run BEFORE the June month data is loaded.** The batch's inbox
  (`app/store.py:get_noted_records`) is every record with a clinical note that hasn't been
  agent-processed yet, with no date filter — every one of the 40 June records also carries
  a note. Load them first and the batch tries to process all 42 noted records at once,
  finds no recorded transcript for that combined message, and errors out. Confirmed by
  running it in the wrong order:
  `FileNotFoundError: No recording for specialist 'clinical' with this exact message`.

So: reset + load the 2 batch fixtures (Step A) → run Segment 1 → run Segment 2 (order-
independent, fine to run here) → THEN load the June month data (Step B/C) → run Segment 3.
That is the exact order below and the exact order to record in.

**One-take consequence:** Step A happens before you press record. Steps B and C happen on
camera, between Segment 2 and Segment 3 — there is no way to pre-load the month without
breaking Segment 1.

### Step A — reset the DB and load the two batch-demo fixtures in hash-matching order

The wow record (`payload_wrong_patient_note.json`) must land at a **lower `run_id`** than
the clean-note record (`payload_note_clean.json`), because that's the order they were in
when the replay transcripts were recorded. `load_results.py --fixtures` glob-sorts
alphabetically ("note_clean" < "wrong_patient_note"), which gets the order backwards — so
this step loads them with a short inline script instead of the CLI.

```
python3 <<'PY'
import json, os
from app.validator import get_validator
from app.router import route
from app.store import init_db, save_report, demographics_from_payload, save_demographics

ORDER = [
    "payload_wrong_patient_note.json",
    "payload_note_clean.json",
    "payload_bad_codes.json",
    "payload_bad_dates.json",
    "payload_bad_values.json",
    "payload_clean.json",
    "payload_missing_fields.json",
]

init_db()
validator = get_validator("local")
demographics_rows = []
for name in ORDER:
    payload = json.load(open(os.path.join("tests/fixtures/payloads", name)))
    report = validator.validate(payload)
    routing = route(report)
    run_id = save_report(report, model=validator.name,
                          source_system=payload.get("metadata", {}).get("source_system"),
                          routing=routing, payload=payload)
    demographics_rows.append(demographics_from_payload(report["payload_id"], payload))
    print(f"  {name:32s} -> {report['status']:4s} ({report['issue_count']} issue(s)) "
          f"{routing['domain']:8s} run_id={run_id}")
save_demographics(demographics_rows)
print("done")
PY
```

**Expected output (verified):**

```
  payload_wrong_patient_note.json  -> pass (0 issue(s)) clean    run_id=1
  payload_note_clean.json          -> pass (0 issue(s)) clean    run_id=2
  payload_bad_codes.json           -> fail (4 issue(s)) billing  run_id=3
  payload_bad_dates.json           -> fail (3 issue(s)) identity run_id=4
  payload_bad_values.json          -> fail (5 issue(s)) identity run_id=5
  payload_clean.json               -> pass (0 issue(s)) clean    run_id=6
  payload_missing_fields.json      -> fail (3 issue(s)) identity run_id=7
done
```

This resets the whole DB (`init_db()` drops and recreates every table). Do NOT load the
June month data yet — Segment 1 (next) needs to run against ONLY these 7 records. The
month-load steps (B and C) come later in this doc, positioned right before Segment 3,
because that's the only point in the sequence where it's safe to run them.

---

## Segment 1 — Nightly agent run (the wow-record batch)

**On camera, in this order:**

### 1a. Run the deterministic validator on the wow payload first — 0 issues

```
python3 -c "
import json
from app.validator import get_validator
p = json.load(open('tests/fixtures/payloads/payload_wrong_patient_note.json'))
r = get_validator('local').validate(p)
print(json.dumps(r, indent=2))
"
```

**Expected output (verified):**

```json
{
  "payload_id": "E-WOW-01",
  "encounter_date": "2024-06-15",
  "status": "pass",
  "issue_count": 0,
  "issues": []
}
```

This is the whole point of the segment: the record is internally consistent (vitals in
range, codes valid, dates sane), so the rules pass it clean. The problem is only visible by
reading the note against the structured data — which is exactly what the agent batch does
next.

### 1b. Run the nightly agent batch

```
python -m app.agents --date 2026-07-14 --mode replay
```

**Expected output (verified, abridged — full JSON has all 4 findings; shown here is the
shape plus the counts block):**

```json
{
  "worklist": [
    {
      "run_id": 1,
      "domain": "identity",
      "field": "patient.sex",
      "problem": "Note describes a male patient ('gentleman') while structured demographics list the patient as female.",
      "severity": "critical",
      "evidence": "62-year-old gentleman with a history of hypertension"
    },
    {
      "run_id": 1,
      "domain": "identity",
      "field": "patient.age",
      "problem": "Note states patient is 62 years old, but structured demographics list age as 34.",
      "severity": "critical"
    },
    {
      "run_id": 1,
      "domain": "clinical",
      "field": "patient_context.age",
      "problem": "Note describes a 62-year-old gentleman but structured patient context lists age 34.",
      "severity": "critical"
    },
    {
      "run_id": 1,
      "domain": "clinical",
      "field": "patient_context.sex",
      "problem": "Note refers to patient as 'gentleman' (male) but structured patient context lists sex as F.",
      "severity": "critical"
    }
  ],
  "dropped": [],
  "counts": {
    "records": 2,
    "returned": 4,
    "kept": 4,
    "dropped": 0,
    "unknown_record": 0,
    "credits_spent": 0
  }
}
```

**Say on camera:** all 4 findings are on `E-WOW-01`, all `critical`, all zero rule issues a
moment ago. Two specialists caught the same patient-identity mismatch independently — the
identity specialist (`patient.*`) and the clinical specialist (`patient_context.*`), which
is why the worklist shows `domain: identity` twice and `domain: clinical` twice rather than
"4 identity" — both readings are the same underlying error (a note copied from a 62-year-old
male patient onto a 34-year-old female patient's chart), caught from two angles.
`credits_spent: 0` — this is replay.

**Fallback still-shot:** the `worklist` array above, screenshotted before scrolling past it.

---

## Segment 2 — Five-try comparison (the thesis scorecard)

Self-contained — reads the 5 canonical fixtures directly, doesn't depend on Segment 1's or
3's DB state. Safe to run any time after Step A.

```
python -m app.agents.compare --runs 5 --mode replay
```

**Expected output (verified, abridged to the per-run counts — the full JSON also includes
per-finding detail and a totals block):**

```json
{
  "runs": [
    {"run_number": 1, "usable": true, "counts": {"caught": 14, "severity_mismatch": 1, "missed": 0, "false_alarm": 0}, "dropped_findings": 0},
    {"run_number": 2, "usable": true, "counts": {"caught": 14, "severity_mismatch": 0, "missed": 1, "false_alarm": 0}, "dropped_findings": 0},
    {"run_number": 3, "usable": true, "counts": {"caught": 15, "severity_mismatch": 0, "missed": 0, "false_alarm": 7}, "dropped_findings": 0},
    {"run_number": 4, "usable": true, "counts": {"caught": 14, "severity_mismatch": 1, "missed": 0, "false_alarm": 4}, "dropped_findings": 0},
    {"run_number": 5, "usable": true, "counts": {"caught": 12, "severity_mismatch": 3, "missed": 0, "false_alarm": 0}, "dropped_findings": 0}
  ],
  "usable_runs": 5,
  "unusable_runs": 0
}
```

**Say on camera:** temperature is 0, same 15 planted issues every try — and the count the
LLM reports still moves try to try (12–15 caught, 0–7 false alarms). That's the reliability
argument before you even get to the accuracy one.

### Then, in the sqlite3 shell: Q8 and Q9

```
sqlite3 -header -column ehr_triage.db
```

Then paste Q9 first (the scorecard — this is the still-shot fallback for this segment):

```sql
SELECT
    cr.run_number,
    cr.mode,
    cr.usable,
    SUM(CASE WHEN res.outcome = 'caught' THEN 1 ELSE 0 END)            AS caught,
    SUM(CASE WHEN res.outcome = 'severity_mismatch' THEN 1 ELSE 0 END) AS misgraded,
    SUM(CASE WHEN res.outcome = 'missed' THEN 1 ELSE 0 END)            AS missed,
    SUM(CASE WHEN res.outcome = 'false_alarm' THEN 1 ELSE 0 END)       AS false_alarms,
    cr.dropped_findings                                                AS junk_findings
FROM comparison_runs cr
LEFT JOIN comparison_results res ON res.comparison_run_id = cr.comparison_run_id
GROUP BY cr.comparison_run_id
ORDER BY cr.mode, cr.run_number;
```

**Expected output (verified):**

```
run_number  mode    usable  caught  misgraded  missed  false_alarms  junk_findings
----------  ------  ------  ------  ---------  ------  ------------  -------------
1           replay  1       14      1          0       0             0
2           replay  1       14      0          1       0             0
3           replay  1       15      0          0       7             0
4           replay  1       14      1          0       4             0
5           replay  1       12      3          0       0             0
```

Then Q8 — the per-problem thesis number:

```sql
SELECT
    cr.mode,
    res.record_id,
    res.field,
    res.rule_severity,
    SUM(CASE WHEN res.outcome = 'missed' THEN 1 ELSE 0 END)           AS times_missed,
    SUM(CASE WHEN res.outcome = 'severity_mismatch' THEN 1 ELSE 0 END) AS times_misgraded,
    COUNT(*)                                                           AS usable_tries
FROM comparison_results res
JOIN comparison_runs cr ON cr.comparison_run_id = res.comparison_run_id
WHERE cr.usable = 1
  AND res.outcome IN ('caught', 'severity_mismatch', 'missed')
GROUP BY cr.mode, res.record_id, res.field, res.rule_severity
ORDER BY cr.mode, times_missed DESC, times_misgraded DESC, res.record_id, res.field;
```

**Expected output (verified, top rows — 15 total, sorted worst-first):**

```
mode    record_id               field                       rule_severity  times_missed  times_misgraded  usable_tries
------  ----------------------  --------------------------  -------------  ------------  ---------------  ------------
replay  payload_bad_dates       metadata.extract_timestamp  warning        1             0                5
replay  payload_missing_fields  encounter.facility_npi      critical       0             2                5
replay  payload_bad_codes       diagnoses[0].code           critical       0             1                5
replay  payload_bad_values      vitals.systolic_bp          critical       0             1                5
replay  payload_missing_fields  patient.dob                 critical       0             1                5
...
```

**Say on camera:** every row here is a rule the deterministic validator catches 5 of 5
times, 100% reproducible — and this table is where the "X of N tries" sentence for the
presentation comes from.

`.quit` to leave the sqlite3 shell.

---

## Segment 3 — Month-end audit

**Load the June month data now — after Segments 1 and 2, not before** (see the
prerequisite-sequence note above for why order matters here).

### Step B — regenerate the June month fixtures (idempotent, fixed seed)

`payloads/` is gitignored, so a fresh checkout won't have `payloads/month/`. This
regenerates it byte-for-byte from the committed seed — safe to run even if the directory
already exists.

```
python scripts/generate_month.py
```

**Expected output (verified):**

```
wrote 40 records to payloads/month
```

### Step C — load the June month data into the DB (append, not reset)

```
python load_results.py --fixtures --payload-dir payloads/month --no-init
```

On camera this prints one line per record — about 45 lines — and scrolls. That's fine; talk
over it ("loading the month's 40 records"). If you'd rather keep the screen quiet, append
`| tail -6`, but run it once in the dry run first to confirm what that leaves on screen — the
tail count below was verified for the unpiped command only.

**Expected output (verified, tail):**

```
  payload_M037.json                -> pass  (0 issue(s))  clean    run_id=44
  payload_M038.json                -> pass  (0 issue(s))  clean    run_id=45
  payload_M039.json                -> pass  (0 issue(s))  clean    run_id=46
  payload_M040.json                -> pass  (0 issue(s))  clean    run_id=47

Loaded 40 fixture(s).

Done. Query with: sqlite3 ehr_triage.db < db/queries.sql
```

`--no-init` appends onto the 7 records from Step A instead of wiping them — Segment 1's
`agent_findings` row must survive this step, and it does (`--no-init` skips `init_db()`).

After Steps A–C, `ehr_triage.db` holds 47 `validation_runs` rows (7 fixtures + 40 June
records) and Segment 3 below is ready to run.

### Run the audit

```
python -m app.agents.audit --month 2026-06 --mode replay --grade
```

**Expected output (verified, abridged to `patterns[].name`/`severity` and the `counts` +
`grades` blocks — the full JSON also includes each pattern's quoted evidence and
hypothesis):**

```json
{
  "report": [
    {"name": "MEDITECH temperature capture defect", "severity": "critical"},
    {"name": "Missing zip code concentrated in Black patients", "severity": "critical"},
    {"name": "Gender-biased chest pain documentation and workup", "severity": "critical"},
    {"name": "Widespread identical templated note text across unrelated patients", "severity": "warning"}
  ],
  "dropped": [],
  "counts": {
    "records": 40,
    "patterns_returned": 4,
    "patterns_kept": 4,
    "evidence_dropped": 0,
    "credits_spent": 0
  },
  "grades": {
    "grades": [
      {"planted_key": "unit_conversion_meditech", "outcome": "caught", "matched_index": 0},
      {"planted_key": "copy_paste_note", "outcome": "caught", "matched_index": 2},
      {"planted_key": "gender_tone_bias", "outcome": "caught", "matched_index": 2},
      {"planted_key": "race_missing_zip", "outcome": "caught", "matched_index": 1}
    ],
    "invented": 1
  }
}
```

**Say on camera:** all 4 planted patterns caught, `credits_spent: 0` (replay). Note honestly
on camera: `copy_paste_note` and `gender_tone_bias` both grade against
`matched_index: 2` — the auditor's "Gender-biased chest pain" pattern is broad enough to
cover both plants, and the grader isn't set up to split credit. Don't oversell this as two
clean independent catches; say what the number says.

### Then, in the sqlite3 shell: Q12 and Q13

```
sqlite3 -header -column ehr_triage.db
```

Q12 first — the deterministic half of the bias finding (SQL alone surfaces the asymmetry;
the LLM only has to name it):

```sql
SELECT
    d.race,
    COUNT(*) AS records,
    SUM(CASE WHEN d.zip IS NULL OR d.zip = '' THEN 1 ELSE 0 END) AS missing_zip,
    ROUND(100.0 * SUM(CASE WHEN d.zip IS NULL OR d.zip = '' THEN 1 ELSE 0 END)
          / COUNT(*), 1) AS missing_zip_pct
FROM record_demographics d
JOIN validation_runs v ON v.payload_id = d.payload_id
GROUP BY d.race
ORDER BY missing_zip_pct DESC;
```

**Expected output (verified — the blank-race row is the 7 batch-demo fixtures from Step A,
which have no `patient.race` field; call that out rather than cutting it):**

```
race      records  missing_zip  missing_zip_pct
--------  -------  -----------  ---------------
Black     10       8            80.0
White     10       0            0.0
Hispanic  10       0            0.0
Asian     10       0            0.0
          7        0            0.0
```

Then Q13 — the auditor scorecard (**this is the still-shot fallback for this segment**):

```sql
SELECT
    g.planted_key,
    g.outcome,
    p.name AS matched_pattern
FROM audit_grades g
JOIN audit_reports r ON r.report_id = g.report_id
LEFT JOIN audit_patterns p ON p.pattern_id = g.matched_pattern_id
ORDER BY g.planted_key;
```

**Expected output (verified):**

```
planted_key               outcome  matched_pattern
------------------------  -------  -------------------------------------------------
copy_paste_note           caught   Gender-biased chest pain documentation and workup
gender_tone_bias          caught   Gender-biased chest pain documentation and workup
race_missing_zip          caught   Missing zip code concentrated in Black patients
unit_conversion_meditech  caught   MEDITECH temperature capture defect
```

`.quit` to leave the sqlite3 shell.

---

## After recording

The DB is left with 47 `validation_runs` rows, 4 `agent_findings`, 5 `comparison_runs` /
86 `comparison_results`, 1 `audit_reports` / 4 `audit_grades`. Re-running Segments 2 or 3
appends more rows rather than erasing anything (safe, but the demo has already been
captured — no need to). To reset for a clean re-recording, start over from Step A.

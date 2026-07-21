# EHR Data Quality Triage Pipeline

A healthcare data-quality pipeline that checks patient-encounter records at the front door.
Built for the USEReady AIxcelerate capstone. **All data is synthetic — no real patient
information.**

## The idea

Broken EHR data poisons everything downstream — billing, analytics, patient safety. The
question this project answers: which jobs belong to plain code, and which belong to an AI agent?

- For **fixed, well-specified rules**, a deterministic Python validator is the right tool —
  faster, cheaper, and it gives the same answer every time.
- The **AI agents exist only for what rules can't reach**: reading clinical notes, catching
  contradictions between fields, and spotting patterns across a whole month of records.

Both engines return the identical JSON, so one database and one set of SQL queries covers both,
and the comparison is fair.

One definition used throughout: **severity means "is this number believable," not "is the patient
in danger."** Blood oxygen above 100% is critical because 100 is the maximum — it's impossible
data, not a dying patient.

## What's in the repo

- `app/validator.py` — the deterministic rules (`LocalValidator`).
- `app/agents/` — the AI layer: specialists, the grounding checker, the month-end auditor, the
  compare harness, and the record/replay transport.
- `db/queries.sql` — the SQL analytics run over persisted results.
- `docs/` — decisions, phase checklist, and the recorded-presentation assets in
  `docs/presentation/`.
- `tests/` — pytest suite over the fixtures (pins validator behavior, incl. the temp-71.2°F guard).

## Quick start

```
python -m pip install -r requirements.txt      # Python 3.12
python -m pytest -q                            # run the tests (should be green)
```

Everything demoable runs in **replay mode** — it re-reads saved API responses instead of paying
for a live call, so it's free and reproducible:

```
python -m app.agents.compare --runs 5 --mode replay      # rules vs. AI, five runs
python -m app.agents.audit --month 2026-06 --mode replay --grade   # month-end auditor
```

Live calls need a Lyzr API key in `.env` and are rate-limited to a small monthly budget — the
tests and demos never need one.

## Stack

Python 3.12 · FastAPI · SQLAlchemy Core (same code runs SQLite locally and Postgres on a server) ·
a Lyzr agent running Claude Sonnet at temperature 0.

Built with Claude Code — the AI wrote much of the code; the decisions stayed mine.

# CLAUDE.md — EHR Data Quality Triage Pipeline

A healthcare EHR data-quality validation pipeline. Portfolio capstone (AiXcelerate / USEReady)
targeting healthcare data-engineering roles. Not production PHI — synthetic data only.

## What it does
One patient-encounter record (JSON) enters → a validator inspects it → produces a structured triage
report (every defect: field path, problem, severity, remediation) → report persisted to a DB → SQL
analytics run across all records to surface data-quality trends.

## The thesis (protect this — it's the presentation argument)
For fixed, well-specified rules, a **deterministic Python validator is the correct tool** — faster,
cheaper, auditable, more reliable than an LLM. The **LLM exists only for what rules can't reach**:
unstructured text, cross-field contradictions, novel patterns. We prove it by running both against
the same records and showing where the LLM silently drops issues the script catches.

## Two engines, one output contract
- `LocalValidator` — deterministic Python rules. Trusted baseline. No external deps.
- `LyzrValidator` — calls a deployed Lyzr agent (Claude Sonnet, temp 0) via API. Creds in `.env`.
Both return identical JSON: `{payload_id, status, issue_count, issues:[{field, problem, severity,
remediation}]}`.

## Severity = plausibility of the datum, NOT patient survivability
- `critical` = definitionally impossible / near-certain data-entry error (SpO2 > 100, HR = 0, age < 0)
- `warning`  = possible but implausible, needs human review (temp 71.2°F — survivable, not a
  plausible entered value)
- `info`     = cosmetic (wrong case on code_system)

## Stack
FastAPI + Uvicorn · SQLAlchemy Core (same code → SQLite local / Postgres on Render) · Lyzr agent
(Claude Sonnet, temp 0) · Python 3.12.8 · macOS/zsh/pyenv · GitHub `airwolff/EHR-Validator`.

## Hard constraints
- Lyzr free tier = **20 credits/month — never bulk-run through the agent** (use the 5 fixtures).
- Lyzr key in `.env` only (rotated after an exposure) — **never commit/echo it.**
- `.env`, `ehr_triage.db`, `payloads/` stay **gitignored.**
- `db/queries.sql`: keep SQL **UPPERCASE**; no autoformatting editors.
- Render free Postgres expires after 30 days (reloadable synthetic data — fine).

## How I work here
- **ELI5:** plain language, exact commands, state expected output, one step at a time, confirm
  before advancing. Flag a flawed premise before answering.
- **Decisions before code.** **Verify by running, not asserting.** **Explicit approval before any
  commit/push.**
- **Commit format `[type] short desc`** (e.g. `[feat]`, `[fix]`, `[data]`, `[docs]`, `[test]`).
  **No `Co-Authored-By: Claude` trailer.** Attribute without personal names ("verified locally").
- **Test-driven where practical:** pin validator behavior with pytest over the 5 fixtures (incl. a
  regression guard on the temp-71.2°F case) before refactoring rules.
- **Code review before merge:** run `/code-review` (or request review) on a finished branch.
- **Blocker Rule:** don't guess — stub, mark `# BLOCKED`, log in open-questions.md, report.

## Docs (start-here order)
1. `docs/phase-checklist.md` — what to work on now (source of truth for scope).
2. `docs/handoff.md` — where the last session left off (verify before trusting).
3. `docs/decisions.md` — the durable "why".
4. `docs/open-questions.md` — what's undecided.
5. `docs/for-review.md` — mentor-checkpoint items + presentation arguments.
6. `docs/cc-onboarding-brief.md` — the original framework brief (background).

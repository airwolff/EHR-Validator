# CC Onboarding Brief — EHR Triage Pipeline

**For:** the Claude Code instance working on the EHR Data Quality Triage Pipeline.
**Repo:** `https://github.com/airwolff/EHR-Validator.git` · **Local:** `~/Desktop/projects/sql_portfolio/ehr-triage`
**What this is:** a working-and-documentation framework, transplanted from another project of Andy's
and adapted to this one. Read this first. Then **create the docs described in §3** and work by the
rules in §2.

---

## 0. TL;DR — do this first

1. Read this brief top to bottom.
2. Create the six docs in §3 (copy the seed content — it's pre-filled with what's already true).
3. From then on, `docs/handoff.md` + `docs/phase-checklist.md` are your "where am I" each session.
4. Follow the working rules in §2 — especially: **decisions before code**, **verify by running,
   not asserting**, and **explicit approval before any commit/push**.

> **ELI5 is on for this project.** Define technical terms in plain language. Give exact commands.
> State the expected output. One step at a time. Confirm the output before advancing. Surface a
> flawed premise before answering a question built on it. This applies to these docs too — keep
> them plain.

---

## 1. The documentation framework (what each file is, and why)

The system separates **four kinds of writing** so each has one home and never gets duplicated. The
core mistake it prevents: dumping status, rationale, and TODOs into one file that nobody trusts.

| File | Role | Lifecycle | In git? |
|---|---|---|---|
| `CLAUDE.md` (repo root) | Always-loaded conventions + pointers. Tight. **No changelog, no status.** | Edit in place; keep small | Yes |
| `docs/decisions.md` | The durable **"why"** — append-only decision log | **Append only.** Never rewrite/delete; supersede with a new dated entry | Yes |
| `docs/open-questions.md` | Decisions **pending** someone else / pending info | Update status as answers arrive | Yes |
| `docs/phase-checklist.md` | The live **"what to work on now"** task tracker for the current phase | Rewritten per phase; tick only when verified | Yes |
| `docs/handoff.md` | Transient **"resume here"** snapshot for the next session | Overwrite each session | Optional (can stay local) |
| `docs/for-review.md` | Running list of items to raise at a **program/mentor checkpoint** + presentation arguments to protect | New up top; resolved → bottom | Yes |
| Memory (`~/.claude/.../memory/`) | Auto-loaded facts/prefs that persist across sessions | Write one fact per file + index line | No (user-global) |
| Git history | The permanent record of *what changed* | — | Yes |

**How they interact (the rule of thumb):**
- *Why did we do it this way?* → `decisions.md` (durable) — the reader a month from now.
- *What's undecided?* → `open-questions.md`.
- *What do I do next?* → `phase-checklist.md`.
- *Where was I / what's the current state?* → `handoff.md` (read it, but **verify before trusting** —
  it's a snapshot and may be stale).
- *A convention that governs all future work?* → `CLAUDE.md` (and maybe a memory).

**Why append-only for decisions.md:** the value is the *reasoning frozen in time*. If a decision
reverses, you add a new entry that says "supersedes 2026-06-20 …" — you never edit the old one. That
way the log shows how thinking evolved, which is exactly what a portfolio reviewer (and future-you)
wants to see.

---

## 2. Working rules (conventions)

### Start each session
1. Read `CLAUDE.md`, then `docs/phase-checklist.md` (what's in scope now), then `docs/handoff.md`
   (where the last session left off).
2. **Verify the repo state before trusting the handoff** (`git status`, `git log --oneline -3`,
   does the server boot). The handoff is a claim, not proof.

### Decisions before code
State the decision and its reasoning **before** writing the implementation. For anything with a
tradeoff, say what you're choosing and why in one or two lines, then act. Log the significant ones in
`decisions.md`.

### The Blocker Rule
When a task depends on something genuinely unresolved (a missing spec, an external dependency you
can't reach, an ambiguous rule you'd have to guess at):
1. **Don't guess. Don't invent.**
2. Scaffold a stub / leave a clearly-marked `# BLOCKED: <what> — see docs/open-questions.md #N`.
3. Stop work on that piece and **report the blocker** before moving on.
4. Add the question to `open-questions.md`.

*This project's realistic blockers:* an ambiguous validation-rule threshold (is X plausible?), a
Lyzr-credit limit (can't test at volume), a deployment prerequisite (Render/Postgres not set up), an
undecided output contract change.

### Verify by running, not by asserting
"Done / passing / works" is a claim you must back with observed output. For a data pipeline this is
non-negotiable:
- Ran the server? Show the boot line / the request + the JSON response.
- Changed the schema? Show a query result proving the column is there and populated.
- Fixed a validator rule? Run it against the fixture and show the issue list.

**"Verified" means *you observed it*, not that it should work.** State the expected output *before*
running, then compare. (This dovetails with the ELI5 standing instruction.)

### Git & approval
- Commit format: `[type] short description` — e.g. `[feat]`, `[fix]`, `[refactor]`, `[data]`,
  `[docs]`, `[test]`. Tight subject; 1–2 line body max, no verbose bullet essays.
- **Explicit approval before any commit or push.** Never commit or push on your own initiative.
- Single remote here (`origin` = GitHub). *(No dual-remote dance — that was another project.)*
- **Do not** add a `Co-Authored-By: Claude` trailer.
- Attribute in docs/commits without personal names ("verified locally", not "Andy confirmed").

### Secrets & data hygiene (hard rules — from the project constraints)
- `.env`, `ehr_triage.db`, `payloads/` are gitignored — **keep them that way; never commit them.**
- The Lyzr API key lives in `.env` only. It was rotated once after an exposure — **never echo it,
  never commit it, never paste it into a doc.**
- **Lyzr free tier = 20 credits/month. Never run bulk records through the Lyzr agent.** Use the 5
  fixtures for agent testing.
- `db/queries.sql` corrupts under autoformatting editors — **keep SQL keywords UPPERCASE**; don't
  open it in an autoformatter.
- Render free Postgres expires after 30 days; synthetic data reloads — not a blocker for a demo.

---

## 3. Seed content — create these files

Copy each block into the named file. They're pre-filled with what's already true so you start with a
real baseline, not empty templates. Treat any *(draft — confirm)* line as a candidate to verify.

---

### `CLAUDE.md` (repo root)

```markdown
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
  commit/push.** Commit `[type] short desc`. No `Co-Authored-By: Claude`.
- **Blocker Rule:** don't guess — stub, mark `# BLOCKED`, log in open-questions.md, report.

## Docs (start-here order)
1. `docs/phase-checklist.md` — what to work on now (source of truth for scope).
2. `docs/handoff.md` — where the last session left off (verify before trusting).
3. `docs/decisions.md` — the durable "why".
4. `docs/open-questions.md` — what's undecided.
5. `docs/for-review.md` — mentor-checkpoint items + presentation arguments.
```

---

### `docs/decisions.md`

```markdown
# Decision Log — EHR Triage Pipeline

**Append-only.** The durable record of *why*. Add a dated entry per significant decision; never
rewrite/delete — if a decision reverses, add a new entry that supersedes it. Format per entry:
**Decision · Why · Refs/supersedes.**

---

## <DATE> — Foundational design (Phase 1)

**Deterministic validator is primary; LLM is for what rules can't reach.** *Why:* fixed rules are
faster, cheaper, auditable, reproducible; the LLM's value is unstructured text / cross-field
contradictions / novel patterns. *Refs:* this is the core presentation thesis.

**Two engines share one JSON output contract** (`payload_id, status, issue_count, issues[]`). *Why:*
identical shape lets us diff LocalValidator vs LyzrValidator on the same records and expose silent
LLM misses.

**Severity encodes plausibility of the entered datum, not patient survivability.** critical =
impossible/near-certain entry error; warning = implausible-but-possible (temp 71.2°F); info =
cosmetic. *Why:* the tool judges data quality, not clinical state.

**Lyzr agent = Claude Sonnet at temp 0.** *Why:* determinism as far as the model allows; this is a
validator, not a creative task.

**SQLAlchemy Core (not the ORM) for persistence.** *Why:* one code path hits SQLite locally and
Postgres on Render via an env-var DB URL; Core keeps SQL explicit and portable without ORM overhead.

**Lyzr is tested on the 5 fixtures only; never bulk-run.** *Why:* free tier = 20 credits/month.

## <DATE> — Lyzr miss on the temp fixture (a finding, not a bug)
The Lyzr agent **missed** `vitals.temp_f = 71.2°F` that LocalValidator caught. *Why it stays:* this
is the demonstration — evidence that an LLM silently drops issues a deterministic rule catches. Do
not "fix" it by tuning the agent to pass; it's the point.

## <DATE> — Phase 2 routing layer
**Field→domain ownership routing** (`app/router.py`): map each field to a domain (billing, clinical,
identity, admin), assign a **priority-ordered primary domain**, and **escalate on any critical
issue**. Four columns added to `validation_runs`: `routing_domain, escalated, routing_reason,
llm_summary`. *Why:* triage needs an owner and an escalation signal, not just a defect list.

**LLM escalation is summary + cross-field contradiction detection — NOT re-validation.** Only
escalated records go to Lyzr; it produces a plain-English `llm_summary`, it does not re-run the
rules. *Why:* credit budget + clean role separation (rules validate, LLM explains/contradicts).
```
*(Replace `<DATE>` with real dates. If you don't know the exact date a Phase-1 decision was made,
use the date you're logging it and say "(logged retroactively)".)*

---

### `docs/open-questions.md`

```markdown
# Open Questions

Decisions pending info or a checkpoint. Do not build past a blocker until RESOLVED.
**Status key:** OPEN | RESOLVED | DEFERRED. Each has a **Blocks:** line naming gated work.

---

## #1 — Web UI scope (draft — confirm)
**Status:** OPEN
Minimal single HTML page served by FastAPI: payload input, results panel, live stats panel. What
exactly does the stats panel show (clean rate? per-source defect rate? escalation count?), and is it
read-only or does it trigger validation?
**Blocks:** the Phase-2 web UI task.

## #2 — Escalation summary surfacing (draft — confirm)
**Status:** OPEN
`llm_summary` is stored per escalated record. Is it shown in the UI, only in SQL analytics, or both?
**Blocks:** UI results panel; possibly an analytics query.

## #3 — Render deployment timing (draft — confirm)
**Status:** OPEN
Postgres swap + Render deploy is a remaining Phase-2 item. Deploy now or after the UI? (Free Postgres
expires in 30 days — don't start the clock before the demo window.)
**Blocks:** Postgres swap, Render deploy.

---
## Resolved
_(move items here with the resolution + date as they close)_
```

---

### `docs/phase-checklist.md`

```markdown
# Phase Checklist — Phase 2 (in progress)

Live tracker for the current phase. Tick a box only when **verified by running it** (not assumed).

## Done this phase
- [x] `store.py` → SQLAlchemy Core, env-var-driven DB URL switching
- [x] Four routing columns on `validation_runs` (routing_domain, escalated, routing_reason, llm_summary)
- [x] `app/router.py` — field→domain map, priority-ordered primary domain, escalate on any critical
- [x] `main.py` wires routing into `/validate`

## Remaining (build order)
- [ ] **Confirm the server boots cleanly** with updated `main.py` — run uvicorn, show the boot line,
      POST one fixture to `/validate`, show the JSON (incl. the new routing fields populated)
- [ ] **LLM escalation** — escalated records only → Lyzr → plain-English summary + cross-field
      contradiction detection (NOT re-validation). Test on fixtures only (credit budget)
- [ ] **Postgres swap + Render deploy** — same SQLAlchemy Core code, switch DB URL (gated by OQ#3)
- [ ] **Minimal web UI** — single HTML page (payload input + results panel + live stats), served by
      FastAPI (gated by OQ#1/#2)

## Per-task loop
decide + note rationale → implement → **run it, observe output vs expected** → get approval → commit
`[type] …` → push (after approval).
```

---

### `docs/handoff.md`

```markdown
# Handoff — EHR Triage Pipeline — <DATE>

Read CLAUDE.md and docs/phase-checklist.md first, then this.

## Repo state (verify before trusting)
- Branch / HEAD: <run `git rev-parse --short HEAD`>
- `git status`: <fill in>
- Does the server boot? <confirm — this is the top remaining task>

## Where we are
Phase 1 complete. Phase 2 in progress. Completed this session: store.py → SQLAlchemy Core; four
routing columns on validation_runs; app/router.py; main.py wired into /validate.

## Next (priority order)
1. Confirm server boots cleanly with updated main.py (run + observe).
2. LLM escalation (escalated records only → summary + contradiction, not re-validation).
3. Postgres swap + Render deploy (OQ#3).
4. Minimal web UI (OQ#1/#2).

## Gotchas / carry-forward
- Never bulk-run Lyzr (20 credits/mo). Fixtures only.
- Keep `.env` / `ehr_triage.db` / `payloads/` gitignored; never commit the Lyzr key.
- Keep `db/queries.sql` UPPERCASE; no autoformatting editors.
- Explicit approval before commit/push. Verify by running, not asserting.
```

---

### `docs/for-review.md`

```markdown
# For Review — mentor checkpoints + presentation arguments

Items to raise at a program/mentor checkpoint, and the core arguments to protect in the write-up/demo.
New up top; resolved → bottom.

## Presentation arguments to protect (don't let refactors erode these)
- Deterministic-first: rules are the trusted baseline; LLM only for what rules can't reach.
- The Lyzr **temp 71.2°F miss** is the headline evidence — keep it visible, don't tune it away.
- Severity = plausibility of the datum, not patient survivability.

## Open / to raise
- Web UI scope + stats-panel contents (see open-questions #1/#2).
- Deploy timing vs the 30-day Postgres clock (open-questions #3).

## Budget / limits
- Lyzr credits: <track usage here> / 20 per month.

## Resolved
_(move here as items close, with date)_
```

---

## 4. Bootstrapping steps (for the receiving CC)

1. Create the six files in §3 (fill `<DATE>` and the *(draft — confirm)* lines).
2. **First real task = the top of the Phase-2 checklist:** confirm the server boots cleanly.
   - Say the expected output first (e.g. "Uvicorn running on http://127.0.0.1:8000").
   - Run it; POST one fixture to `/validate`; show the JSON with the new routing fields populated.
   - Only then tick the box.
3. Log any decision you make in `decisions.md`; park anything you'd have to guess at in
   `open-questions.md` and report it.
4. Ask for approval before the first commit; then commit the new docs as `[docs] add working +
   decision framework`.

---

### One-line summary for the receiving CC
> Read this brief, create the six docs, then work the Phase-2 checklist top-down — decisions before
> code, verify by running, approval before commit. The temp-71.2°F Lyzr miss is a feature of the
> story, not a bug to fix.

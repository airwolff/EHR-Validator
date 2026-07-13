# Decision Log — EHR Triage Pipeline

**Append-only** (ADR-lite). The durable record of *why*. One decision per entry; never rewrite/delete
— if a decision reverses, add a new entry that **supersedes** the old one (name it).

**Log a decision when** it is hard to reverse, involves a real trade-off, affects multiple parts, or
the same question has been debated twice.

**Entry format:** **Decision** · **Status** (accepted | proposed | superseded by &lt;date&gt;) · **Why**
(context + rationale) · **Consequences** (what it commits us to / gives up) · **Refs** (spec/plan/files).
*(Older entries below predate this format and keep Decision · Why · Refs — that's fine; append-only.)*

---

## 2026-07-08 — Foundational design (Phase 1) *(logged retroactively)*

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

## 2026-07-08 — Lyzr miss on the temp fixture (a finding, not a bug) *(logged retroactively)*
The Lyzr agent **missed** `vitals.temp_f = 71.2°F` that LocalValidator caught. *Why it stays:* this
is the demonstration — evidence that an LLM silently drops issues a deterministic rule catches. Do
not "fix" it by tuning the agent to pass; it's the point.

## 2026-07-08 — Phase 2 routing layer *(logged retroactively)*
**Field→domain ownership routing** (`app/router.py`): map each field to a domain (billing, clinical,
identity, admin), assign a **priority-ordered primary domain** (identity > billing > clinical >
admin), and **escalate on any critical issue**. Four columns added to `validation_runs`:
`routing_domain, escalated, routing_reason, llm_summary`. *Why:* triage needs an owner and an
escalation signal, not just a defect list.

**LLM escalation is summary + cross-field contradiction detection — NOT re-validation.** Only
escalated records go to Lyzr; it produces a plain-English `llm_summary`, it does not re-run the
rules. *Why:* credit budget + clean role separation (rules validate, LLM explains/contradicts).

## 2026-07-08 — Boot fix: main.py resynced with store.py + router.py
`main.py` was out of sync with the Phase-2 refactor: it imported `DB_PATH` (removed from `store.py`
when it moved to `DATABASE_URL`), so the server would not even import; and it never called
`app/router.py`, so routing was dead code. **Fixed:** import `ensure_tables`/`save_report`/
`get_stats`; call `route(report)` in `/validate` and persist `routing`; delegate `/stats` to
`store.get_stats()` (which adds the domain breakdown). *Why:* the prior handoff ticked these boxes
without running the app — verified this time by booting uvicorn and POSTing a fixture.

**`init_db()` (DROP+CREATE) split from `ensure_tables()` (CREATE-if-missing).** Boot now calls
`ensure_tables()` — non-destructive. *Why:* the old lifespan risked wiping the DB; `init_db` stays
available for an explicit reset only.

## 2026-07-08 — Merged working practices into the framework
Adopted, on top of the onboarding brief: **(1) TDD** — pin validator behavior with pytest over the 5
fixtures, including a regression guard on the temp-71.2°F miss; **(2) code review before merge** via
`/code-review`. *Why:* the brief had "verify by running" but no test suite and no review step; these
close the gap without changing the thesis. Commit-convention overrides (`[type]` format, no Claude
trailer) also saved to project memory so they persist across sessions.

## 2026-07-11 — Formalized the session-handoff protocol
**Decision:** Add `docs/session-protocol.md` (start/end-of-session ritual + git-based staleness check
+ quality gate), upgrade `handoff.md` to a staleness-block + "dead ends" template, and tighten this
log to ADR-lite (Status + Consequences). Handoff history = overwrite + git history (no archive
folder). No separate project "memory doc." · **Status:** accepted · **Why:** a thorough scan of
external best practice (ADRs; Claude Code / agent session-handoff guidance) converged on what the
onboarding brief already sketched, but flagged three gaps we had — recording *what's actually in
place* (not "done"), capturing *failed attempts*, and *verifying handoffs against git before
trusting them*. Sessions span days here, so stale handoffs are a real risk. · **Consequences:** one
more doc to keep current each session; in exchange, a fresh session can reconstruct state reliably.
The memory/`decisions.md`/`handoff.md` boundary is now written down so nothing gets duplicated. ·
**Refs:** `docs/session-protocol.md`, `docs/handoff.md`.

## 2026-07-13 — Test fixtures are tracked under `tests/fixtures/payloads/`
**Decision:** The test suite reads payloads from `tests/fixtures/payloads/` (committed to git), not
from the repo-root `payloads/` dir. The 5 canonical fixtures are copied there; the 2 demo payloads
added in plan Task 11 go there too. `/payloads/` stays gitignored as pure generator output. This
resolves the implementation plan's one open item (Task 11 note, line 1209). · **Status:** accepted ·
**Why:** `payloads/` is fully gitignored and *nothing in it was ever tracked*, so the plan's original
`conftest.py` (reading `../payloads`) would make `pytest` die with `FileNotFoundError` on any fresh
clone — the test suite is portfolio evidence a mentor or recruiter is meant to clone and run, so it
must be green with no generation step. Rejected auto-generating in `conftest` (a generator bug would
then masquerade as a test failure, and a regression guard must pin behavior against a *frozen* file,
not a regenerated one). Rejected `!payloads/*.json` un-ignore negations (a half-tracked/half-ignored
dir is how a file you meant to keep out eventually leaks). · **Consequences:** the 5 canonical
payloads exist in two places; the tracked copies are golden files and may intentionally drift from
`generate_payloads.py` — if the generator changes, the golden copies are updated deliberately, not
silently. Also required anchoring the ignore pattern to `/payloads/`: unanchored `payloads/` matches
at *any* depth and was silently ignoring `tests/fixtures/payloads/` too. · **Refs:** `.gitignore`,
`tests/conftest.py`, plan `docs/superpowers/plans/2026-07-09-multi-agent-triage.md` (Tasks 1, 11).

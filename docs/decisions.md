# Decision Log — EHR Triage Pipeline

**Append-only.** The durable record of *why*. Add a dated entry per significant decision; never
rewrite/delete — if a decision reverses, add a new entry that supersedes it. Format per entry:
**Decision · Why · Refs/supersedes.**

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

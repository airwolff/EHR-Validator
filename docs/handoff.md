# Handoff — EHR Triage Pipeline — 2026-07-11 (updated)

Read `CLAUDE.md` and `docs/phase-checklist.md` first, then this. See `docs/session-protocol.md` for
how to use/update this file. **Verify the staleness block below before trusting anything here.**

## ⚠️ CONCURRENCY WARNING
Two CC sessions touched this repo. **Run exactly ONE session going forward.** A second session
committed the baseline (below) while a first was mid-work. Before continuing, confirm no other
session is open.

## Staleness block (check before trusting)
- **Written:** 2026-07-11 (updated after a concurrent session committed)
- **HEAD at write time:** `4fea28d` (branch `main`)
- **Uncommitted at write time:** `M CLAUDE.md, docs/decisions.md, docs/handoff.md` · `?? docs/session-protocol.md`
  — these are the **session-handoff-system upgrade** (this session), not yet committed.
- **Boots?** Yes — `python -c "import app.main"` → OK (verified 2026-07-11).
- **Staleness test:** if `git rev-parse --short HEAD` ≠ `4fea28d` or `git status -s` differs from the
  line above, this handoff is stale — trust git + code, rewrite this early.

## Where we are
- **Baseline is COMMITTED** at `4fea28d`: Phase-2 wiring (`main.py`/`store.py`/`router.py` resynced,
  boots), plus the framework docs, the approved spec, and the approved plan.
  - Spec: `docs/specs/2026-07-08-multi-agent-triage-design.md`
  - Plan: `docs/superpowers/plans/2026-07-09-multi-agent-triage.md` (12 TDD tasks)
- **Task 1 is NOT started** — verified: no `tests/`, no `app/agents/`, no `pytest` in `requirements.txt`.
- **Uncommitted:** the session-handoff protocol (`docs/session-protocol.md` + edits to `CLAUDE.md`,
  `decisions.md`, this file). Safe on disk; needs a commit.
- Execution mode chosen: **subagent-driven**.

## ► Next step (do this first)
1. Confirm exactly one session is open. Run the start-of-session staleness check (`docs/session-protocol.md`).
2. **Commit the pending handoff-protocol docs:** `[docs] add session-handoff protocol` (files:
   `docs/session-protocol.md`, `CLAUDE.md`, `docs/decisions.md`, `docs/handoff.md`).
3. Decide the plan's one open item — fixture location (recommend `tests/fixtures/payloads/`).
4. **Start Task 1** (pytest harness + temp-71.2 regression guard), then proceed through the plan.
   - *Task-1 preconditions pre-verified 2026-07-11 (ran the validator directly): `LocalValidator.validate()`
     exists; `payloads/payload_bad_values.json` → exactly 1 `vitals.temp_f` issue @ `critical`;
     `payloads/payload_clean.json` → status `pass`, 0 issues. Both fixtures match the plan's filenames.
     The two guard tests should therefore PASS on first run — a red result means a fixture drifted;
     stop and inspect before writing more.*

## Open decision (not blocking the build)
- **Lyzr deployment:** (a) one generic agent, prompts in our `specialists.py` [recommended] vs (b) two
  deployed agents. Only needed at Task 12; needs the user to create the agent in Lyzr Studio + put
  `agent_id`/key in `.env`.

## Dead ends — don't retry
- **Don't trigger the agents off `escalated`/rule-criticals.** The nightly batch selects on
  **note-presence** — a zero-rule-issue record (the wow catch) must still be processed.
- **Don't edit `router.py`'s `DOMAIN_PRIORITY`.** Worklist precedence is a *separate* sort.
- **Don't bulk-run `LyzrValidator` per-record** (20 credits/mo). Task 12 gates it behind the ledger.
- **Don't run two CC sessions on this repo at once** (this is why the earlier handoff went stale).

## Gotchas / carry-forward
- Lyzr = **20 credits/month**; fixtures/replay only. Keep `.env` / `ehr_triage.db` / `payloads/` gitignored.
- `db/queries.sql` UPPERCASE; no autoformatter. Commit `[type] short desc`; **no `Co-Authored-By: Claude`**.
- **Explicit approval before any commit/push.** Verify by running, not asserting.

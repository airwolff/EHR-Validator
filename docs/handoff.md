# Handoff — EHR Triage Pipeline — 2026-07-08

Read CLAUDE.md and docs/phase-checklist.md first, then this.

## Repo state (verify before trusting)
- Branch / HEAD: `main` @ `7126649` (run `git rev-parse --short HEAD` to confirm).
- `git status`: modified `app/store.py`, `app/main.py`, `requirements.txt`; new `app/router.py`,
  `CLAUDE.md`, and the `docs/*.md` framework files. **Not yet committed** (awaiting approval).
- Does the server boot? **Yes — verified this session.** `python -m uvicorn app.main:app` boots;
  `/health` → `{"status":"ok","engine":"local"}`; POST a fixture to `/validate` returns the report
  with a populated `routing` block; `/stats` returns severity + domain breakdowns.

## Where we are
Phase 1 complete. Phase 2 in progress. This session: resynced `main.py` with the Phase-2 refactor
(it imported a removed `DB_PATH` and never called the router — the server couldn't even import);
wired `route()` into `/validate`; split `init_db` (destructive) from `ensure_tables` (safe boot);
deduped `/stats` onto `store.get_stats()`. Created CLAUDE.md + the six-doc framework from the
onboarding brief, corrected to the verified state. Merged in two practices: TDD and code-review.

## Next (priority order)
1. **Test suite** — pytest over the 5 fixtures + temp-71.2°F regression guard (new merged practice).
2. LLM escalation (escalated records only → summary + contradiction, not re-validation).
3. Postgres swap + Render deploy (OQ#3).
4. Minimal web UI (OQ#1/#2).

## Gotchas / carry-forward
- Never bulk-run Lyzr (20 credits/mo). Fixtures only.
- Keep `.env` / `ehr_triage.db` / `payloads/` gitignored; never commit the Lyzr key.
- Keep `db/queries.sql` UPPERCASE; no autoformatting editors.
- `ehr_triage.db` holds exactly the 5 fixture rows — verification POSTs write extra rows; clean them
  up (or reload) so the demo DB stays at 5.
- Commit `[type] short desc`, **no `Co-Authored-By: Claude`**. Explicit approval before commit/push.

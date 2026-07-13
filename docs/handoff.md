# Handoff — EHR Triage Pipeline — 2026-07-13

Read `CLAUDE.md` and `docs/phase-checklist.md` first, then this. See `docs/session-protocol.md` for
how to use/update this file. **Verify the staleness block below before trusting anything here.**
(A `SessionStart` hook now runs that check for you automatically and will say STALE if it drifted.)

## Staleness block (check before trusting)
- **Written:** 2026-07-13
- **HEAD at write time:** `6e2ba6a` (branch `main`, in sync with `origin/main`)
- **Uncommitted at write time:** none — working tree clean.
- **Tests:** `python -m pytest -q` → **2 passed** (verified 2026-07-13).
- **Boots?** Yes — `python -c "import app.main"` → `boots` (verified 2026-07-13).
- **Staleness test:** if `git rev-parse --short HEAD` ≠ `6e2ba6a` or `git status -s` is non-empty,
  this handoff is stale — trust git + code, rewrite it early.

## Where we are

**Plan Task 1 is DONE and pushed.** Everything before it (Phase-2 routing, server boot) was already
green. Tasks 2–12 are untouched.

- **Test harness exists** — `tests/`, pytest 8.3.4, 2 passing tests in
  `tests/test_validator_baseline.py`. The temp-71.2°F regression guard is **proven to bite**: widening
  the `temp_f` hard bound in `app/validator.py:49` flips the finding `critical`→`warning` and reds the
  test. It is a real guard, not a vacuous one.
- **Fixtures are tracked at `tests/fixtures/payloads/`** (5 canonical payloads). The repo-root
  `payloads/` stays gitignored as pure generator output. Rationale in `docs/decisions.md` (2026-07-13).
  `git clone && pip install -r requirements.txt && pytest` is now green with no generation step.
- **The rules are now enforced by hooks, not memory** (`.claude/`, all verified by triggering them):
  - `git commit`/`push` is **blocked** if pytest is red or a secret is staged.
  - `docs/decisions.md` rejects any edit that removes text (append-only). Append at the end only.
  - `db/queries.sql` rejects lowercase SQL keywords.
  - The handoff staleness check runs at every session start.
  - A **`/handoff` skill** runs this end-of-session ritual.

## ► Next step (do this first)

**Plan Task 2 — sex-restricted diagnosis-code rule.** This is a genuine red-green TDD cycle (unlike
Task 1, whose tests locked existing behavior and passed immediately).

Plan: `docs/superpowers/plans/2026-07-09-multi-agent-triage.md` → "Task 2" (line ~102). It is fully
specified — test, implementation, and commit message are all written out. In order:

1. Write `tests/test_validator_sex_codes.py` (given in the plan).
2. Run `python -m pytest tests/test_validator_sex_codes.py -v` → **must FAIL** (no `patient.sex`
   issue is produced yet). If it passes, stop — something is wrong with the premise.
3. Add `SEX_RESTRICTED_CODES` + section 6 to `app/validator.py` (given in the plan).
4. Re-run with `tests/test_validator_baseline.py` → all green.
5. `/code-review`, get approval, commit `[feat] add sex-restricted diagnosis-code rule to LocalValidator`.

Then Tasks 3→12 in order. Execution mode chosen: **subagent-driven**.

## Open decisions (not blocking the build)

- **Lyzr deployment shape:** (a) one generic agent with prompts in our `specialists.py`
  [recommended] vs (b) two deployed agents. Only needed at **Task 12**; needs you to create the agent
  in Lyzr Studio and put `agent_id`/key in `.env`.
- `docs/open-questions.md` **#1, #2, #3 are still OPEN** — they gate the Web UI and the Render
  deploy, i.e. the *last two* checklist items. They do **not** block Tasks 2–12.

## Dead ends — don't retry

- **Don't trigger the agents off `escalated`/rule-criticals.** The nightly batch selects on
  **note-presence** — a zero-rule-issue record (the wow catch) must still be processed.
- **Don't edit `router.py`'s `DOMAIN_PRIORITY`.** Worklist precedence is a *separate* sort.
- **Don't bulk-run `LyzrValidator` per-record** (20 credits/mo). Task 12 gates it behind the ledger.
- **Don't port `duly_noted`'s `post-edit-format.sh` hook.** It autoformats `*.md`/`*.json` and would
  reformat `db/queries.sql`, which this project forbids.
- **Don't run two CC sessions on this repo at once** (this is what made the 2026-07-11 handoff stale).

## Gotchas / carry-forward

- **Stale `.pyc` can lie to you.** Python's bytecode cache validates on source *size + mtime-seconds*.
  Editing and reverting a file within the same second, with the same byte count, makes Python re-run
  the **old** bytecode — tests then fail against source that is provably clean. If a result makes no
  sense, `find . -name __pycache__ -type d -exec rm -rf {} +` and re-run.
- **A crashing hook silently stops guarding.** Claude Code treats a non-2 exit as a *soft* error and
  runs the tool anyway. Both hooks fail **open, deliberately**, on an unparseable payload. If you edit
  them, keep that property — and test with `printf`, never `echo` (zsh's `echo` mangles `\n` and will
  feed the hook invalid JSON).
- **`.gitignore` patterns match at any depth.** `payloads/` was silently ignoring
  `tests/fixtures/payloads/` too; it is now anchored as `/payloads/`. Check `git check-ignore -v <path>`
  before assuming a new file is trackable.
- Lyzr = **20 credits/month**; fixtures/replay only. Keep `.env` / `ehr_triage.db` / `payloads/` gitignored.
- Commit `[type] short desc`; **no `Co-Authored-By: Claude` trailer**. **Explicit approval before any
  commit/push.** Verify by running, not asserting.

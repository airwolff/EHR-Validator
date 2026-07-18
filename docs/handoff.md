# Handoff — EHR Triage Pipeline — 2026-07-18

Read `CLAUDE.md` and `docs/phase-checklist.md` first, then this. See `docs/session-protocol.md` for
how to use/update this file. **Verify the staleness block below before trusting anything here.**
(A `SessionStart` hook runs that check automatically and will say STALE if it drifted.)

## Staleness block (check before trusting)
- **Written:** 2026-07-18
- **HEAD at write time:** `cc37c0a` (branch `main`, pushed, in sync with `origin/main`). The commit
  that carries this handoff is one `[docs]` commit on top of it — that alone is not drift.
- **Uncommitted at write time:** clean (this file is the only change, committed right after).
- **Tests:** `python -m pytest -q` → **181 passed in 0.94s** (verified 2026-07-18)
- **Boots?** Yes — `python -c "import app.main"` → `boots` (verified 2026-07-18)
- **Staleness test:** if HEAD moved past the docs commit or `git status -s` differs, trust git +
  code and rewrite this early.

## ⚠️ Before auditing or "fixing" anything
The code deliberately disagrees with `docs/superpowers/plans/2026-07-09-multi-agent-triage.md` in
~20 places. Every deviation is a recorded decision in `docs/decisions.md` (each dated entry names
its plan task and what it deviates from) and is pinned by a named test. **Read `decisions.md`
first; the plan is a historical document.** Reverting a deviation because "the plan says otherwise"
reintroduces a bug we already paid to find.

## Where we are

**The build is complete. Task 13 — the thesis-as-evidence experiment — ran live 2026-07-16,
is graded, replay-verified, committed, and written into the docs.** All plan tasks plus Task 13
are done, verified by running, and pushed.

The Task 13 result (numbers from SQL over the persisted grades, not estimates):
- N=5 live tries over the same 5 fixtures; the **only variable was record order** in the message
  (fixed rotation). All 5 replies usable, 0 quarantined — the Task-12 JSON-escape contract rule held.
- **Rules:** identical 15/15 problems, every try. **LLM:** a different answer every try —
  1 silent miss (`metadata.extract_timestamp` warning, 1/5), 5 misgrades (missing facility NPI,
  a critical, downgraded 2/5; malformed diagnosis code / impossible BP / missing DOB once each),
  11 invented problems (`encounter_id` on 4 rule-clean records in 2 tries; `patient.age` once on
  the certified-clean record).
- Recordings committed (`app/agents/recordings/comparison-*.json`, commit `47d2868`) — the whole
  run replays offline for free: `python -m app.agents` comparison mode, `--mode replay`.
- Analytics live in `db/queries.sql` (miss rate, scorecard, confusion, reliability — `3910cb1`).

**Credits:** ledger 10/15 spent; Lyzr sidebar ≈8.8 left on the free 20/month (resets Aug 11).
This session's spend: 5 tries + 1 lost to a 60s timeout (fix: timeout now configurable via `.env`,
junk value refuses before the charge — `549c2c1`). Starter was never purchased or needed (OQ #6).

The presentation argument — both halves, with the slide sentence — is in `docs/for-review.md`.
The full experiment rationale is `docs/decisions.md` (2026-07-17 entry).

## ► Next step (do this first)

**The AiXcelerate window (Jul 8–17) is over. Shift to the presentation/write-up.**
`docs/for-review.md` holds the argument structure, both thesis halves with measured numbers, and
the exact slide sentence — start there. The demo story: live wow-record catch (Half 1) + the
five-try comparison replayed offline (Half 2), both from committed recordings, zero credits.

If build work resumes instead, the remaining checklist items are gated on Andy's answers to
`docs/open-questions.md` #1–#3 (web UI scope, escalation surfacing, Render deploy timing) —
ask, don't assume. The adjudicator agent stays deferred (OQ #5).

## Dead ends — don't retry
- **Don't re-run the live comparison to "confirm."** Temp 0 does not make tries identical (that's
  the finding), a re-run costs real credits, and replay already reproduces the graded run
  byte-for-byte. New live runs need a fresh reason and Andy's OK.
- **Don't set the Lyzr timeout to 60s** or trust the old default: one credit died to a 60s attempt
  before `549c2c1`. Timeout comes from `.env` now; a junk value refuses before charging.
- The full pre-Task-13 dead-end list (unmetered bulk path, caller-side gate, unescaped-quote JSON
  failure, per-mode Q8/Q10 double-count) is recorded in `docs/decisions.md` 2026-07-14→17 entries —
  each is pinned by a test; don't re-litigate.

## Gotchas / carry-forward
- **Severity ladder:** plausibility of the datum, NOT survivability (`CLAUDE.md`). The temp-71.2°F
  case is a warning, and it's the Phase-1 anecdote — the *measured* headline is the Task-13
  five-try result (see `for-review.md`; misses moved around between runs, which is itself the point).
- **`db/queries.sql` must stay UPPERCASE** (hook-enforced) and `decisions.md` is append-only
  (hook-enforced — reversals are new entries, never edits).
- **Quarantined `.rejected` recordings are evidence, committed on purpose** — don't clean them up.
- Replay is free and needs no `.env` key; only `--mode live` touches Lyzr, and it's ledger-gated
  inside `LyzrValidator.validate` itself.
- `payloads/`, `.env`, `ehr_triage.db` are gitignored — a fresh clone needs `.env` recreated
  (Lyzr key + timeout) and data reloaded before live anything; replay + pytest work immediately.

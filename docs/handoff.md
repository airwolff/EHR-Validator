# Handoff — EHR Triage Pipeline — 2026-07-19

Read `CLAUDE.md` and `docs/phase-checklist.md` first, then this. See `docs/session-protocol.md`
for how to use/update this file.

## Staleness block (check before trusting)
- **Written:** 2026-07-19
- **HEAD at write time:** `80cb847` (branch `main`; the commit carrying this handoff is one
  `[docs]` commit on top — that alone is not drift)
- **Uncommitted at write time:** clean (this file + decisions entry are the only changes,
  committed right after)
- **Tests:** `python -m pytest -q` → **181 passed in 0.83s** (verified 2026-07-19)
- **Boots?** Yes — `python -c "import app.main"` → `boots` (verified 2026-07-19)
- **Staleness test:** if HEAD moved past the docs commit or `git status -s` differs, trust git +
  code and rewrite this early.

## Where we are

**The pipeline build is complete (through Task 13). This session designed the final
presentation AND a new build item — the month-end auditor agent — and produced an approved
spec and a full implementation plan. NOTHING from that plan is built yet; no plan code has
been written or run.**

- Spec (approved by Andy): `docs/superpowers/specs/2026-07-18-month-end-auditor-design.md`
  (commit `0494f7f`). The why lives there and in `docs/decisions.md` 2026-07-19 entry.
- Plan (12 tasks, full code in steps): `docs/superpowers/plans/2026-07-18-month-end-auditor.md`
  (commit `80cb847`). Tasks 1–6 = TDD build of the auditor; Task 7 = **Andy-gated live run
  (1 credit)**; Tasks 8–12 = docs, runbook, script, deck, handoff.

**The deadline that drives everything:** AiXcelerate presentation slot is **Tue Jul 21,
9:30–11:00 EST** (Mahima's reschedule email, Jul 16). Andy may not be able to attend and asked
to submit a **recorded video on YouTube** — no confirmed answer, a "second slot" was mentioned.
Requirements from Mahima's Jul 1 email: **15 minutes**, must cover **Project Objective, Live
Project Demo, Key Outcomes, Way Forward** (these four appear verbatim as slide labels in the
plan). Working assumption: **the recording must exist by end of Mon Jul 20.**

Presentation decisions (all settled with Andy — do not re-ask):
- **Recorded video**, 15 min; audience = cohort + hiring team + mentor.
- **HTML deck published as a private Artifact**, presented full-screen while recording.
- **Three live screen-recorded demo segments**, all from committed replay recordings, zero
  credits: nightly batch (wow record), five-try comparison, month-end audit.
- **Story-first structure** (minute map in the spec) with rubric headings on slides.
- **Script in Andy's voice** — profile saved to Claude memory (`andy-writing-voice`):
  numbers first, short declaratives, comma splices, plain verbs, no hype, no exclamation marks.

**Credits:** ledger 10/15 spent, sidebar ≈8.8 left (resets Aug 11). The plan budgets ≤2 live
audit calls. Nothing was spent this session.

## ► Next step (do this first)

**Execute the plan, Task 1** (`docs/superpowers/plans/2026-07-18-month-end-auditor.md`),
via superpowers:subagent-driven-development (recommended in-plan) or executing-plans.
Two open items Andy has NOT yet answered — ask before the first commit:
1. Execution approach (subagent-driven vs inline).
2. Blanket approval for the plan's per-task commits (messages are written in the plan).
   Without it, pause for approval at every commit. **Task 7's live call is a hard stop for
   Andy's explicit go-ahead regardless.**

**The fallback rule is in the spec and is binding:** if the auditor isn't graded and green by
end of Sat Jul 19 (hard: Sun morning), it drops to Way Forward, Demo 3 is cut, and the deck
ships with the two-demo map. The presentation never waits on the agent.

## Dead ends — don't retry
- **Don't re-run the Task-13 live comparison to "confirm"** — temp 0 doesn't make tries
  identical (that's the finding); replay reproduces the graded run for free.
- **Don't trust the old 60s Lyzr timeout**; it ate a credit once. Set `LYZR_TIMEOUT_SECONDS=180`
  in `.env` before the live audit call — the audit message is ~4× the comparison message.
- The full pre-Task-13 dead-end list is in `docs/decisions.md` 2026-07-14→17 entries, each
  pinned by a test; don't re-litigate.
- Gmail MCP token expired once mid-session; if mail is needed again and errors, Andy re-auths
  via `/mcp` → claude.ai Gmail.

## Gotchas / carry-forward
- **Report month is `2026-06` everywhere** (generator SEED 20260601, tests, demo commands).
- **Message purity is load-bearing** for the auditor exactly as for the specialists: the audit
  message is fingerprinted for replay — `sort_keys=True`, sorted corpus, no timestamps.
- **Generator determinism is tested** (same seed → identical bytes). If a planted-rate test
  fails, adjust the seed constant, not the assertions.
- **Answer key terms ↔ grading tests are coupled** (`scripts/audit_answer_key.json` ↔
  `tests/test_audit_grading.py`) — change them together.
- **Bias framing rule** (spec + prompt): the auditor flags documentation bias IN THE DATA on a
  synthetic corpus with planted defects; it does not diagnose people or accuse clinicians.
- Severity ladder = plausibility of the datum, NOT survivability (`CLAUDE.md`).
- `db/queries.sql` UPPERCASE keywords (hook), `decisions.md` append-only (hook), quarantined
  `.rejected` recordings are committed evidence, `payloads/`/`.env`/`ehr_triage.db` gitignored.
- Replay is free and needs no `.env` key; only `--mode live` touches Lyzr, ledger-gated.
- The 5 canonical fixtures live in `tests/fixtures/payloads/`; the generated month will live in
  `payloads/month/` (gitignored — the committed generator script recreates it byte-identically).

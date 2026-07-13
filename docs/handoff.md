# Handoff — EHR Triage Pipeline — 2026-07-13

Read `CLAUDE.md` and `docs/phase-checklist.md` first, then this. See `docs/session-protocol.md` for
how to use/update this file. **Verify the staleness block below before trusting anything here.**
(A `SessionStart` hook runs that check automatically and will say STALE if it drifted.)

## Staleness block (check before trusting)
- **Written:** 2026-07-13
- **HEAD at write time:** `cf78881` (branch `main`, in sync with `origin/main`)
- **Uncommitted at write time:** none — `git status -s` empty.
- **Tests:** `python -m pytest -q` → **30 passed** (verified 2026-07-13).
- **Boots?** Yes — `python -c "import app.main"` → `boots` (verified 2026-07-13).
- **Staleness test:** if `git rev-parse --short HEAD` ≠ `cf78881` or `git status -s` is non-empty,
  this handoff is stale — trust git + code, rewrite it early.

## Where we are

**Plan Tasks 1–4 are DONE and pushed. Tasks 5–12 are untouched.** Everything so far is the
deterministic rules + persistence layer. **No Lyzr call has been made** — that is by design (credit
budget); the agent layer starts at Task 5.

Landed this session (each verified by running, not asserting):

- **Task 2 — sex-restricted diagnosis-code rule** (`9153fcf`). Fires `critical` on `patient.sex`
  when a sex-restricted ICD code contradicts a *definitely stated* M/F (pregnancy code on M,
  prostate code on F). Two things beyond the plan, both from `/code-review`:
  - The plan's code compared `sex == "M"` against a `.upper()`ed diagnosis code. A record with
    `"sex": "m"` came back `status: pass`, `issue_count: 0`, **not escalated** — a silent false
    negative in the engine the whole presentation argues is the *trustworthy* one. Sex is now
    normalised (`_normalise_sex`).
  - **`patient.sex` was removed from `REQUIRED`.** Declining to state sex previously scored
    `critical` ("Required field is missing or empty") — the same severity as `SpO2 = 105`. An
    undeclared sex (absent, `unknown`, `other`, **"prefer not to say"**) now yields **no issue at
    any severity** and *suppresses* the sex-restricted rule (no asserted sex ⇒ nothing to
    contradict). Unmappable junk (e.g. `"42"`) is `info`, aimed at the ingest mapping. Full
    rationale in `docs/decisions.md` (2026-07-13).
- **Task 3 — `labs[]` + ordered-vs-resulted rule** (`1a04253`). `warning` on either mismatch. Beyond
  the plan: lab fields had **no entry in the router**, so they hit the `admin` catch-all
  (`app/router.py:63`). Lab defects now route to **clinical** — otherwise the domain breakdown in
  the SQL analytics would have read "admin" for every missing lab result. (This adds a prefix to
  `_field_to_domain`; it does **not** touch `DOMAIN_PRIORITY` — see Dead ends.)
- **Task 4 — persist `payload_json`** (`cf78881`). Every run now stores the raw record beside its
  report, so a finding traces back to its source data and the Task-10 nightly batch has the note to
  read. Beyond the plan: **`load_results.py` was not routing at all** — every row in the demo DB had
  `routing_domain = NULL`, so `/stats` and the domain analytics reported *nothing* by domain. The
  loader and `/validate` had silently drifted. `save_reports_bulk` now takes
  `(report, source_system, routing, payload)` and both writers persist the same thing.

Current demo DB (reloaded 2026-07-13 via `python load_results.py --fixtures`), from `get_stats()`:

```
total_runs: 5   passed: 1   pass_rate_pct: 20.0
issues_by_severity: {critical: 11, warning: 3, info: 1}
records_by_domain:  {billing: 1, clean: 1, identity: 3}
```

## ► Next step (do this first)

**Plan Task 5 — `agent_findings` table + save/query functions.** This is where the Lyzr/agent layer
begins. Plan: `docs/superpowers/plans/2026-07-09-multi-agent-triage.md` → "Task 5" (line 377); it
specifies the test, the schema, and the commit message.

The design point to protect: agent findings live in a **separate table** from `validation_issues`, so
rule-caught and LLM-caught defects are never mixed. That separation *is* the presentation argument —
at demo time you show exactly which engine caught what.

Same loop as Tasks 2–4: write the failing test → run it and **watch it fail** → implement →
`/code-review` → get approval → commit → push. Then Tasks 6→12 in order.

## Open decisions (not blocking the build)

- **Lyzr deployment shape:** (a) one generic agent with prompts in our `specialists.py`
  [recommended] vs (b) two deployed agents. Only needed at **Task 12**; needs you to create the
  agent in Lyzr Studio and put `agent_id`/key in `.env`.
- `docs/open-questions.md` **#1, #2, #3 are still OPEN** — they gate the Web UI and the Render
  deploy, i.e. the *last two* checklist items. They do **not** block Tasks 5–12.

## Dead ends — don't retry

- **Don't trigger the agents off `escalated`/rule-criticals.** The nightly batch selects on
  **note-presence** — a zero-rule-issue record (the wow catch) must still be processed.
- **Don't edit `router.py`'s `DOMAIN_PRIORITY`.** Worklist precedence is a *separate* sort. (Adding
  a field→domain *prefix* to `_field_to_domain`, as Task 3 did for `labs[`, is a different thing and
  is fine.)
- **Don't bulk-run `LyzrValidator` per-record** (20 credits/mo). Task 12 gates it behind the ledger.
- **Don't port `duly_noted`'s `post-edit-format.sh` hook.** It autoformats `*.md`/`*.json` and would
  reformat `db/queries.sql`, which this project forbids.
- **Don't run two CC sessions on this repo at once** (this is what made the 2026-07-11 handoff stale).

## Gotchas / carry-forward

- **A schema change needs a real DB reset — `ensure_tables()` will NOT save you.** It is
  `metadata.create_all`, which creates missing *tables* but **never adds a column to an existing
  table**. Add a column and the app still boots clean, then dies on the first insert with
  `no such column`. Tests never catch this (each builds a fresh DB); only the long-lived
  `ehr_triage.db` does. After any column addition run `python load_results.py --fixtures` (drops,
  recreates, reloads the 5 fixtures — synthetic, safe).
- **When two code paths write the same table, a test must pin both.** Task 4's `payload_json` test
  passed while the *bulk* path silently dropped both payload and routing. Nothing failed loudly: the
  column existed, the inserts succeeded, the numbers were just empty.
- **`/code-review` is earning its keep.** It caught the `"sex": "m"` false negative and the labs
  routing skew — both silent, both would have survived a green suite. Run it before every commit.
- **Stale `.pyc` can lie to you.** Bytecode is validated on source *size + mtime-seconds*. Edit and
  revert a file within the same second, same byte count, and Python re-runs the **old** bytecode. If
  a result makes no sense: `find . -name __pycache__ -type d -exec rm -rf {} +` and re-run.
- **A crashing hook silently stops guarding.** Claude Code treats a non-2 exit as a *soft* error and
  runs the tool anyway. Both hooks fail **open, deliberately**, on an unparseable payload. If you
  edit them, keep that property — and test with `printf`, never `echo` (zsh's `echo` mangles `\n`
  and will feed the hook invalid JSON).
- **`.gitignore` patterns match at any depth.** `payloads/` was silently ignoring
  `tests/fixtures/payloads/` too; it is now anchored as `/payloads/`. Check
  `git check-ignore -v <path>` before assuming a new file is trackable.
- **Pre-existing quirk, left alone:** *any* issue — even an `info` — sets `status: "fail"`. So a
  record whose only defect is an unmappable sex string reads as a failed record. Revisit only if it
  muddies the demo.
- Lyzr = **20 credits/month**; fixtures/replay only. Keep `.env` / `ehr_triage.db` / `payloads/`
  gitignored.
- Commit `[type] short desc`; **no `Co-Authored-By: Claude` trailer**. **Explicit approval before
  any commit/push.** Verify by running, not asserting.

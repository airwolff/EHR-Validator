# Handoff — EHR Triage Pipeline — 2026-07-13

Read `CLAUDE.md` and `docs/phase-checklist.md` first, then this. See `docs/session-protocol.md` for
how to use/update this file. **Verify the staleness block below before trusting anything here.**
(A `SessionStart` hook runs that check automatically and will say STALE if it drifted.)

## Staleness block (check before trusting)
- **Written:** 2026-07-13
- **HEAD at write time:** `c50244d` (branch `main`, in sync with `origin/main`)
- **Uncommitted at write time:** ` M CLAUDE.md` (new communication rules; commit with this handoff)
- **Tests:** `python -m pytest -q` → **64 passed** (verified 2026-07-13)
- **Boots?** Yes — `python -c "import app.main"` → `boots` (verified 2026-07-13)
- **Staleness test:** if `git rev-parse --short HEAD` ≠ `c50244d` or `git status -s` differs, this
  handoff is stale — trust git + code, rewrite it early.

## Where we are

**Plan Tasks 1–6 DONE and pushed. Tasks 7–13 untouched.** Still **zero Lyzr calls made** — by
design. Correct the old handoff's claim that "Task 5 starts the Lyzr layer": it does not.
**Only Task 12 makes a live call.** Tasks 7–11 run against *recorded* responses and cost nothing.

Landed this session (each verified by running):

- **Task 5 — `agent_findings` table + batch inbox** (`57816d8`). Agent findings live in their own
  table, never in `validation_issues` — that separation *is* the presentation argument. Two
  deviations from the plan, both deliberate:
  - The plan's `get_noted_records(batch_date)` **never used its own `batch_date` param**. It now
    takes **no** date. The inbox is `payload_json IS NOT NULL AND agent_processed_at IS NULL`.
  - New column **`agent_processed_at`**, stamped for every record the batch reads — *including ones
    it clears*. A cleared record writes zero findings, so "no findings" cannot mean "not processed"
    or the batch re-reads (and re-pays for) every clean record forever.
  - The plan's `save_agent_findings` + `mark_processed` pair is collapsed into **one function in one
    transaction**: `record_agent_result(run_id, findings, batch_date)`. Two calls had two silent
    failure modes (die between them → findings written twice on the next run; stamp-then-fail → the
    record leaves the inbox forever with its defects unreported). Both now unreachable.
- **Task 6 — finding schema + evidence guard** (`c50244d`). `app/agents/schema.py`, pure functions.
  Four deviations, all from `/code-review`:
  - `partition_findings` returns `(kept, dropped)` with **all** reasons per drop. The plan discarded
    them — but **the drop rate IS the thesis evidence** ("the agent cited text that isn't in the note
    for M of N findings"). Reasons are collected in full, not first-match-wins, or the hallucination
    rate is undercounted by whatever share of bad findings were *also* malformed.
  - `is_valid_finding` validates **values**, not just key presence. `severity: "banana"` used to pass
    — and `store.WORKLIST_DOMAIN_ORDER` sorts an unknown domain *silently last*, so junk would reach
    the DB and sink in the worklist unseen (the Task-3 labs skew, again).
  - **`MIN_EVIDENCE_CHARS = 6`.** The plan accepted any substring, so a model could "ground" a wholly
    invented finding on `"a"` or `"the"`. 6 blocks that while keeping real short quotes ("A1c 6.9",
    "room air").
  - **Unicode punctuation folded** in `_norm`. Models re-type quotes with curly apostrophes; unfolded,
    a *real* finding gets dropped as `evidence_not_in_note` — a **false hallucination inflating the
    exact number the presentation rests on**.

Current demo DB (reloaded 2026-07-13 via `python load_results.py --fixtures`): 5 runs, 1 passed,
`{critical: 11, warning: 3, info: 1}`, domains `{billing: 1, clean: 1, identity: 3}`.

## ► Next step (do this first)

**Plan Task 7 — credit ledger.** `docs/superpowers/plans/2026-07-09-multi-agent-triage.md` line 618.
Note the ledger's cap is now **raised, not removed** (see Lyzr Starter below) — keep the ledger; it
is a real engineering artifact and a portfolio talking point, not a free-tier workaround.

Same loop as Tasks 2–6: failing test → **watch it fail** → implement → `/code-review` → approval →
commit → push.

## Open decisions

- **`.env` still needs `agent_id` + Lyzr key** — create the agent in Lyzr Studio. **Deferred to Task
  12 by decision** (open-questions #4). Nothing before Task 12 needs it. Their Studio layout changed
  recently — search current docs, don't trust old instructions.
- `docs/open-questions.md`: **#1/#2/#3 OPEN** (gate the Web UI + Render deploy, i.e. the *last* two
  checklist items — they do not block Tasks 7–13). **#4 RESOLVED**, **#5 DEFERRED** (adjudicator).

## Dead ends — don't retry

- **The agent inbox is EMPTY until Task 11.** `get_noted_records()` returns `[]` against the real
  demo DB — **no current fixture has a `clinical_note`**. This is expected, not a bug. Task 11 adds
  the noted fixtures (plan lines 1116/1133), including the zero-rule-issue record the agents catch
  and the rules miss. **Nothing moves end-to-end before Task 11** — consider pulling it ahead of
  Task 10 if you want to watch the pipeline actually run.
- **The evidence guard is NOT an injection defence** — the plan calls it one; that claim is wrong and
  we've stopped making it. An attack carried *in the note* is, by construction, a verbatim quote of
  the note, so the guard keeps it. Also **verbatim ≠ faithful**: the note says "Denies dysuria" and a
  model can claim the patient *has* it while citing "dysuria". Both limits are **pinned by
  `test_LIMIT_*` tests in `tests/test_agents_schema.py`** — they are documented limits, **not bugs to
  fix**. A human adjudicates the worklist; that is the mitigation, and it is *why* the output is a
  worklist and not an auto-correction. See `docs/for-review.md`.
- **Don't add an LLM router** to look more agentic. A deterministic router already does that job —
  swapping in a model puts an LLM exactly where rules *do* reach, undermining the thesis.
- **Don't trigger the agents off `escalated`/rule-criticals.** Selection is on **note-presence** — a
  zero-rule-issue record (the wow catch) must still be processed.
- **Don't edit `router.py`'s `DOMAIN_PRIORITY`.** Worklist precedence (`store.WORKLIST_DOMAIN_ORDER`)
  is a *separate* sort.
- **Don't rip out record/replay or the credit ledger** now that credits are plentiful — see below.
- **Don't run two CC sessions on this repo at once** (this is what made the 2026-07-11 handoff stale).

## Gotchas / carry-forward

- **Lyzr upgraded to Starter — $19/mo, 2,000 credits** (was 20). A batch run is ~2 credits, so ~1,000
  runs/mo vs ~10 *total* on free. **Architecture unchanged.** Record/replay and the ledger stay:
  network-free tests are correct engineering regardless of budget, and a hard spend-gate is a
  talking point. What it bought is **evidence** — the rules-vs-LLM comparison can now be run N times
  and reported as a number. That's **new Task 13** on the checklist. See `docs/decisions.md`.
- **`VALID_DOMAINS` (schema.py) and `WORKLIST_DOMAIN_ORDER` (store.py) must stay identical.** Pinned
  by `test_valid_domains_match_the_worklist_sort_order`. A domain valid in one and unranked in the
  other sorts silently to the bottom of the worklist.
- **A schema change needs a real DB reset — `ensure_tables()` will NOT save you.** It is
  `metadata.create_all`: it creates missing *tables* but **never adds a column to an existing table**.
  The app boots clean, then dies on first insert with `no such column`. Tests never catch it (fresh
  DB each). After any column addition: `python load_results.py --fixtures`.
- **When two code paths write the same table, a test must pin both.** Task 4's `payload_json` test
  passed while the *bulk* path silently dropped payload and routing.
- **`/code-review` keeps earning its keep.** It caught the `"sex": "m"` false negative (Task 2), the
  labs routing skew (Task 3), the un-routing loader (Task 4), the two-transaction findings hole
  (Task 5), and the trivially-defeatable evidence check + the Unicode false-hallucination (Task 6).
  Every one was silent and would have survived a green suite. Run it before every commit.
- **Stale `.pyc` can lie to you.** Bytecode is validated on source *size + mtime-seconds*. If a result
  makes no sense: `find . -name __pycache__ -type d -exec rm -rf {} +` and re-run.
- **A crashing hook silently stops guarding.** Both hooks fail **open, deliberately**. If you edit
  them, keep that property — and test with `printf`, never `echo`.
- **`.gitignore` patterns match at any depth.** Check `git check-ignore -v <path>` before assuming a
  new file is trackable.
- **Pre-existing quirk, left alone:** *any* issue — even an `info` — sets `status: "fail"`.
- **Communication:** be a robot, not a friend — report output, don't narrate or sell the work. Every
  choice gets a one-sentence pro **and** con. Now in `CLAUDE.md`.
- Commit `[type] short desc`; **no `Co-Authored-By: Claude` trailer**. **Explicit approval before any
  commit/push.** Verify by running, not asserting.

# Handoff — EHR Triage Pipeline — 2026-07-13

Read `CLAUDE.md` and `docs/phase-checklist.md` first, then this. See `docs/session-protocol.md` for
how to use/update this file. **Verify the staleness block below before trusting anything here.**
(A `SessionStart` hook runs that check automatically and will say STALE if it drifted.)

## Staleness block (check before trusting)
- **Written:** 2026-07-13
- **HEAD at write time:** `8d9c3e3` (branch `main`, in sync with `origin/main`)
- **Uncommitted at write time:** clean
- **Tests:** `python -m pytest -q` → **141 passed** (verified 2026-07-13)
- **Boots?** Yes — `python -c "import app.main"` → `boots` (verified 2026-07-13)
- **Staleness test:** if `git rev-parse --short HEAD` ≠ `8d9c3e3` or `git status -s` differs, this
  handoff is stale — trust git + code, rewrite it early.

## ⚠️ READ THIS BEFORE AUDITING OR "FIXING" ANYTHING

**The code deliberately disagrees with the plan in ~15 places.** Every one of them was a
`/code-review` finding, each is recorded in `docs/decisions.md`, and each is pinned by a named test.
An auditor (or a fresh session) reading `docs/superpowers/plans/2026-07-09-multi-agent-triage.md`
side-by-side with the code **will find all of them and want to revert them.** Reverting any one
silently reintroduces a bug we already paid to find.

**Read `docs/decisions.md` FIRST. Treat everything in it as settled** unless you can show the
*reasoning* is wrong — not merely that the code differs from the plan. The plan is a historical
document; `decisions.md` supersedes it.

The load-bearing deviations, by task:

| Task | Plan says | Code does | Reverting it causes |
|---|---|---|---|
| 5 | `get_noted_records(batch_date)`; save + mark as two calls | no date param; **one transaction** (`record_agent_result`) | findings written twice, or a record leaves the inbox with defects unreported |
| 6 | `keep_grounded` discards drops; any substring is evidence | `partition_findings` returns **all drops with reasons**; `MIN_EVIDENCE_CHARS=6`; Unicode folded | the drop rate (the thesis evidence) is uncountable; a model "grounds" an invented finding on `"a"`; a curly apostrophe reads as a hallucination |
| 7 | lifetime credit counter, hardcoded budget | **per-month buckets**, `LYZR_CREDIT_BUDGET` (default 15), `flock`, fail-closed on corrupt | cap blocks a fresh billing month; two processes both slip past the budget; a corrupt ledger reads as "0 spent" |
| 8 | recordings keyed by **specialist name** | keyed by specialist **+ fingerprint of the message**; stored question re-checked on read | **one patient's answer served for another patient's chart, silently** |
| 8 | `ledger=None` in live mode = no cap | live mode **refuses** without a ledger | an unbudgeted live path |
| 9 | `parse_findings` returns `[]` on junk | **raises `ResponseUnparseable`** | a broken agent scores as a *perfect* one, and Task 13's miss rate measures silence |
| 9 | contract names fields but never defines them | contract **enumerates domains/severities from `schema.py`'s own constants** | the model's sensible guess is tallied as *its* unreliability — our prompt's defect on its scorecard |
| 10 | stamp only records that HAVE findings | **stamp every record**, cleared ones included | every clean record re-read and re-paid for, forever |
| 10 | write per specialist | **one write per record**, all specialists together | a crash mid-batch stamps a record with half a review — permanently |
| 10 | (no such case) | unreadable reply **aborts the batch + quarantines the recording** | a junk recording replays forever and wedges the pipeline offline |

## Where we are

**Plan Tasks 1–10 DONE and pushed. Tasks 11–13 untouched. Still ZERO Lyzr calls made** — by design.
**Only Tasks 12 and 13 spend credits** (~2 per batch run; Task 13 is ~2×N). Task 11 costs nothing: a
recording is just a file we write.

Landed this session (Tasks 7–10), each verified by running:

- **Task 7 — credit ledger** (`3b0d20c`). `app/agents/ledger.py`. Per-month buckets, `flock` across
  the read-modify-write (the concurrency test **reds without it** — two threads both read 14/15 and
  both wrote 15), atomic writes, `LedgerCorrupt` rather than "0 spent". Budget from
  `LYZR_CREDIT_BUDGET`, **default 15** — free-tier-safe, so cancelling Starter needs no code change.
- **Task 8 — record/replay transport** (`240d685`). `app/agents/transport.py` is the **only** code
  that talks to Lyzr. Recordings are filed under specialist + fingerprint of the exact message.
- **Task 9 — specialists** (`a988e09`). `app/agents/specialists.py`. Clinical and identity agents,
  each seeing only its own slice. **The Task-8 determinism trap is CLOSED** — shuffled records
  produce an identical fingerprint (demonstrated outside pytest).
- **Task 10 — nightly batch** (`8d9c3e3`). `app/agents/batch.py`. **Ran end-to-end against a real
  SQLite DB:** a record that passes every deterministic rule → the identity agent catches the
  wrong-patient note → `{records: 1, returned: 3, kept: 1, dropped: 2, unknown_record: 1}`. That
  single run *is* the presentation: rules find nothing, the LLM finds the real thing, and **2 of the
  3 things it said were junk** — caught, counted, never shown to a human.

## ► Next step (do this first)

**Plan Task 11 — demo fixtures + end-to-end test.** Plan line ~1116.

Two payloads: `payloads/payload_wrong_patient_note.json` (every structured field valid, note
describes a different person — the wow catch) and `payloads/payload_note_clean.json` (note agrees
with the data — the false-positive guard, must yield **zero** findings).

**The plan's recorded responses for Task 11 are STALE — do not copy them.** They are named
`identity.json` / `clinical.json` and their findings carry `encounter_id`. Recordings are now keyed
by a fingerprint of the message (Task 8) and findings carry `record_id` (Task 9). **Generate them
from the real `build_message()` output** — `tests/test_agents_batch.py::record_reply` already does
exactly this and is the pattern to copy. Costs nothing.

Same loop as Tasks 2–10: failing test → **watch it fail** → implement → `/code-review` → approval →
commit → push.

## Open decisions

- **`.env` still needs `LYZR_AGENT_ID` + the key** — create the agent in Lyzr Studio. Needed for
  **Task 12 only**. Their Studio layout changed recently — search current docs, don't trust old
  instructions.
- `docs/open-questions.md`: **#1/#2/#3 OPEN** (gate the Web UI + Render deploy — the *last* two
  checklist items; they do not block Tasks 11–13). **#4 RESOLVED**, **#5 DEFERRED** (adjudicator).

## Dead ends — don't retry

- **The evidence guard is NOT an injection defence**, and **verbatim ≠ faithful** (the note says
  "Denies dysuria"; a model can claim the patient HAS it while quoting "dysuria"). Both limits are
  pinned by `test_LIMIT_*` in `tests/test_agents_schema.py`. They are **documented limits, not bugs
  to fix**. A human adjudicates the worklist — that is the mitigation, and it is *why* the output is
  a worklist and not an auto-correction.
- **Don't add an LLM router.** A deterministic router already does that job; swapping in a model
  puts an LLM exactly where rules *do* reach, undermining the thesis.
- **Don't trigger the agents off `escalated`/rule-criticals.** Selection is on **note-presence** — a
  zero-rule-issue record (the wow catch) must still be processed.
- **Don't edit `router.py`'s `DOMAIN_PRIORITY`.** Worklist precedence (`store.WORKLIST_DOMAIN_ORDER`)
  is a *separate* sort.
- **Don't rip out record/replay or the credit ledger** now that credits are plentiful. Network-free
  tests are correct engineering at any budget, and a hard spend-gate is a talking point.
- **Don't run two CC sessions on this repo at once** (this is what made the 2026-07-11 handoff stale).

## Gotchas / carry-forward

- **Recordings are committed, and that is deliberate** (`app/agents/recordings/`). Synthetic data
  only. It is what lets a fresh clone — or a mentor — run the whole pipeline offline for free.
- **`VALID_DOMAINS` (schema.py) and `WORKLIST_DOMAIN_ORDER` (store.py) must stay identical.** Pinned
  by a test. A domain valid in one and unranked in the other sorts silently to the bottom.
- **The specialist prompts are generated from `schema.py`'s constants.** Don't hardcode the domain
  list into the prompt — that is how the prompt and the guard drift apart, and the drift is scored
  against the model.
- **A schema change needs a real DB reset — `ensure_tables()` will NOT save you.** It is
  `metadata.create_all`: it creates missing *tables*, never adds a column to an existing one. After
  any column addition: `python load_results.py --fixtures`.
- **`fcntl` is POSIX-only** (ledger + batch locks). Fine on macOS and Render; revisit on Windows.
- **In live mode the credit is charged BEFORE the call**, so a Lyzr 500 still costs one. Deliberate —
  charging afterwards lets a runaway loop drain the budget before the ledger hears about it. Do not
  reorder; the docstring says so for a reason.
- **`/code-review` keeps earning its keep.** It caught the `"sex": "m"` false negative (T2), the labs
  routing skew (T3), the un-routing loader (T4), the two-transaction findings hole (T5), the
  trivially-defeatable evidence check (T6), the wrong gitignore path + the self-bricking float spend
  (T7), the cross-patient recording bug (T8), the prose-wrapped-answer false failure (T9), and the
  same-day empty worklist + the pipeline-wedging junk recording (T10). **Every one was silent and
  would have survived a green suite. Run it before every commit.**
- **Stale `.pyc` can lie to you.** If a result makes no sense:
  `find . -name __pycache__ -type d -exec rm -rf {} +` and re-run.
- **Communication:** be a robot, not a friend. **No unexplained jargon — including in design
  discussions.** Every choice gets a one-sentence pro **and** con.
- Commit `[type] short desc`; **no `Co-Authored-By: Claude` trailer**. **Explicit approval before any
  commit/push.** Verify by running, not asserting.

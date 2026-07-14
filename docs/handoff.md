# Handoff — EHR Triage Pipeline — 2026-07-14

Read `CLAUDE.md` and `docs/phase-checklist.md` first, then this. See `docs/session-protocol.md` for
how to use/update this file. **Verify the staleness block below before trusting anything here.**
(A `SessionStart` hook runs that check automatically and will say STALE if it drifted.)

## Staleness block (check before trusting)
- **Written:** 2026-07-14
- **HEAD at write time:** `efa0881` (branch `main`, in sync with `origin/main`). The commit that
  carries this handoff is one `[docs]` commit on top of it — that alone is not drift.
- **Uncommitted at write time:** the four doc files of the end-of-session ritual (this file,
  `decisions.md`, `phase-checklist.md`, `open-questions.md`), committed together right after.
- **Tests:** `python -m pytest -q` → **152 passed** (verified 2026-07-14)
- **Boots?** Yes — `python -c "import app.main"` → `boots` (verified 2026-07-14)
- **Staleness test:** if HEAD moved past the docs commit or `git status -s` differs, trust git +
  code and rewrite this early.

## ⚠️ Before auditing or "fixing" anything
The code deliberately disagrees with `docs/superpowers/plans/2026-07-09-multi-agent-triage.md` in
~20 places. Every deviation is a recorded decision in `docs/decisions.md` (each dated entry names
its plan task and what it deviates from) and is pinned by a named test. **Read `decisions.md`
first; the plan is a historical document.** Reverting a deviation because "the plan says otherwise"
reintroduces a bug we already paid to find.

## Where we are

**Plan Tasks 1–12 DONE, verified by running, and pushed. The first LIVE Lyzr runs happened
2026-07-14.** Total live spend so far: **4 credits** (ledger and Lyzr agree).

What exists now, all verified by running:

- **Task 11** (`7abc91d`, `44d3fd2`): demo fixtures at `tests/fixtures/payloads/`
  (`payload_wrong_patient_note.json` — passes every rule, note describes a different person;
  `payload_note_clean.json` — must yield zero findings). E2e suite `tests/test_e2e_wow_catch.py`
  includes a mixed-batch attribution test. Shared test helpers live in `tests/conftest.py`
  (`fresh_store` fixture with restore-reload, `record_reply`, `save_noted_record`) — use those,
  don't hand-roll store reloads.
- **Task 12** (`bfdd145`, `efa0881`): CLI `python -m app.agents --date YYYY-MM-DD --mode
  replay|live`. The credit gate lives **inside `LyzrValidator.validate`** (config checks → charge →
  network via `transport.call_lyzr_live`) so every caller is metered — including
  `load_results.py --engine lyzr`, which used to bypass it entirely. `BudgetExceeded` → HTTP 429,
  `LedgerCorrupt` → 503. CLI loads `.env` itself and prints one-line refusals.
- **The live agent:** "EHR Batch Specialist" in Lyzr Studio (`anthropic/claude-sonnet-5`, temp 0,
  Memory OFF, no features/tools), a three-sentence passthrough shell — the real prompt rides inside
  each message from `specialists.py`. Its id is in `.env` as `LYZR_BATCH_AGENT_ID`
  (`LYZR_AGENT_ID` stays pointed at the Phase-1 validator agent).
- **The live story so far:** run 1 aborted — the identity agent's reply broke JSON on an unescaped
  double-quote (`("gentleman")`); the batch wrote nothing, kept the inbox, and quarantined the
  reply (`app/agents/recordings/identity-c5a33ce664c6.json.rejected`, **committed as Task-13
  evidence**). `_CONTRACT` gained a JSON-escape rule. Run 2: **4 grounded critical findings on the
  wow record** (both specialists, sex + age each), clean record cleared, 0 dropped, replay
  reproduces it offline for free. The local demo DB (`ehr_triage.db`) holds runs 1–7 and the
  2026-07-14 worklist.

## ► Next step (do this first)

**Design and run Task 13** (rules-vs-LLM comparison, ~2 credits × N runs). **No plan section exists
for it** — it was added to `docs/phase-checklist.md` on 2026-07-13. Brainstorm/plan first, per the
per-task loop. The raw material is ready: 5 canonical fixtures with known rule verdicts (incl. the
temp-71.2°F case), `BatchAborted.credits_spent`, the counted drops, and one real unusable-reply
data point (1 of 2 live runs).

**Budget constraint (settled 2026-07-14, OQ #6):** the account is the **free tier — Starter was
never purchased** (OQ #4 wrongly recorded it as bought; Andy will buy only if needed).
**~14.8 credits remain this month.** A batch run costs ~2 credits regardless of how many records
are in it (one message per specialist), so **size Task 13 at N ≤ 5 runs (~10 credits)** or have
Andy buy Starter first. The repo ledger reads 4 (it only meters gated calls); Lyzr's sidebar is
the number that pays bills.

After Task 13: web UI + Render deploy remain, gated by OQ #1/#2/#3.

## Dead ends — don't retry

- **Don't retry a failed live call without changing the message.** Temperature 0: same message in,
  same broken reply out. Run 1's failure was deterministic; the fix was a contract edit, and the
  retry only made sense after it. A retry costs ~2 credits.
- **Don't hand-author recording files.** They're keyed by a fingerprint of the exact message; a
  hand-written one never replays. Generate via `tests/conftest.py::record_reply` (tests) or a live
  run (demo).
- **Don't add a spend gate back into `app/main.py` or the CLI** — it's inside
  `LyzrValidator.validate` / `transport.get_response` now; a caller-side copy re-creates the
  double-charge bug the review killed.
- **The evidence guard is NOT an injection defence, and verbatim ≠ faithful** — documented limits,
  pinned by `test_LIMIT_*`; a human adjudicates the worklist. Don't "fix" them.
- **Don't add an LLM router / Managerial agent / SuperFlow.** Deterministic orchestration is the
  thesis (`docs/for-review.md` has the rehearsed answer). Lyzr's Groundedness/Reflection/LLM-as-
  Judge features were deliberately left off: they'd hide the very numbers we count.
- **Don't edit `router.py`'s `DOMAIN_PRIORITY`** (worklist order is `store.WORKLIST_DOMAIN_ORDER`,
  a separate sort), and **don't trigger agents off `escalated`** — selection is note-presence.
- **Don't run two CC sessions on this repo at once.**

## Gotchas / carry-forward

- **Any edit to `specialists.py` prompt text orphans every recording** (new message → new
  fingerprint). Expect to re-record live (~2 credits) after any prompt change; delete orphaned
  recordings, keep `.rejected` evidence files.
- **The live worklist ≠ the authored test narrative, on purpose.** Live agents caught the wow
  record 4 ways; the e2e tests replay their own authored recordings and pin 1. Both are correct;
  don't "fix" either to match the other.
- **In live mode the credit is charged BEFORE the network call** (and after the free config
  checks). Do not reorder — the ordering is the fix for two separate review findings.
- **`LYZR_BATCH_AGENT_ID` vs `LYZR_AGENT_ID`:** batch CLI prefers the former, falls back to the
  latter. The Phase-1 agent has its own baked-in prompt — pointing the batch at it produces junk.
- **Recordings are committed, `.rejected` included — deliberate** (offline demo for a fresh clone;
  failure evidence for Task 13). `*.lock` sidecars are gitignored.
- **A schema change needs a real DB reset** — `ensure_tables()` never adds columns. After any
  column addition: `python load_results.py --fixtures --payload-dir tests/fixtures/payloads`
  (note: that loads all 7 tracked fixtures, including the two noted demo records).
- **`fcntl` is POSIX-only** (ledger + batch locks) — fine on macOS/Render, revisit on Windows.
- **`/code-review` before every commit.** This session it caught: the unmetered bulk-lyzr path, the
  charge-before-config-check ordering, the vacuous clean-note test (proven by experiment), the
  missing mixed-batch coverage, and the wow note inviting a live clinical finding — which the live
  run then demonstrated. Every one was invisible to a green suite.
- **Communication: everything ELI5, including reports and review summaries** (repeat correction
  2026-07-14 — "the way you're writing is tough for me to understand"). Plain sentences, terms
  glossed on first use, before/after stories instead of jargon; no JSON blobs at Andy. Every choice
  gets a one-sentence pro AND con. Robot, not friend.
- Commit `[type] short desc`; no `Co-Authored-By` trailer; **explicit approval before any
  commit/push**; verify by running, not asserting.

# Decision Log — EHR Triage Pipeline

**Append-only** (ADR-lite). The durable record of *why*. One decision per entry; never rewrite/delete
— if a decision reverses, add a new entry that **supersedes** the old one (name it).

**Log a decision when** it is hard to reverse, involves a real trade-off, affects multiple parts, or
the same question has been debated twice.

**Entry format:** **Decision** · **Status** (accepted | proposed | superseded by &lt;date&gt;) · **Why**
(context + rationale) · **Consequences** (what it commits us to / gives up) · **Refs** (spec/plan/files).
*(Older entries below predate this format and keep Decision · Why · Refs — that's fine; append-only.)*

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

## 2026-07-11 — Formalized the session-handoff protocol
**Decision:** Add `docs/session-protocol.md` (start/end-of-session ritual + git-based staleness check
+ quality gate), upgrade `handoff.md` to a staleness-block + "dead ends" template, and tighten this
log to ADR-lite (Status + Consequences). Handoff history = overwrite + git history (no archive
folder). No separate project "memory doc." · **Status:** accepted · **Why:** a thorough scan of
external best practice (ADRs; Claude Code / agent session-handoff guidance) converged on what the
onboarding brief already sketched, but flagged three gaps we had — recording *what's actually in
place* (not "done"), capturing *failed attempts*, and *verifying handoffs against git before
trusting them*. Sessions span days here, so stale handoffs are a real risk. · **Consequences:** one
more doc to keep current each session; in exchange, a fresh session can reconstruct state reliably.
The memory/`decisions.md`/`handoff.md` boundary is now written down so nothing gets duplicated. ·
**Refs:** `docs/session-protocol.md`, `docs/handoff.md`.

## 2026-07-13 — Test fixtures are tracked under `tests/fixtures/payloads/`
**Decision:** The test suite reads payloads from `tests/fixtures/payloads/` (committed to git), not
from the repo-root `payloads/` dir. The 5 canonical fixtures are copied there; the 2 demo payloads
added in plan Task 11 go there too. `/payloads/` stays gitignored as pure generator output. This
resolves the implementation plan's one open item (Task 11 note, line 1209). · **Status:** accepted ·
**Why:** `payloads/` is fully gitignored and *nothing in it was ever tracked*, so the plan's original
`conftest.py` (reading `../payloads`) would make `pytest` die with `FileNotFoundError` on any fresh
clone — the test suite is portfolio evidence a mentor or recruiter is meant to clone and run, so it
must be green with no generation step. Rejected auto-generating in `conftest` (a generator bug would
then masquerade as a test failure, and a regression guard must pin behavior against a *frozen* file,
not a regenerated one). Rejected `!payloads/*.json` un-ignore negations (a half-tracked/half-ignored
dir is how a file you meant to keep out eventually leaks). · **Consequences:** the 5 canonical
payloads exist in two places; the tracked copies are golden files and may intentionally drift from
`generate_payloads.py` — if the generator changes, the golden copies are updated deliberately, not
silently. Also required anchoring the ignore pattern to `/payloads/`: unanchored `payloads/` matches
at *any* depth and was silently ignoring `tests/fixtures/payloads/` too. · **Refs:** `.gitignore`,
`tests/conftest.py`, plan `docs/superpowers/plans/2026-07-09-multi-agent-triage.md` (Tasks 1, 11).

## 2026-07-13 — Enforce the written rules with hooks + a handoff skill
**Decision:** Adopt `.claude/` infra (tracked, shared): a `handoff` skill, a pytest/secret
pre-commit gate, an append-only + invariants guard, and an auto-running start-of-session staleness
check. Ported from the sibling repos (`railyard`, `obp/website`, `duly_noted`). · **Status:**
accepted · **Why:** the rules in CLAUDE.md and `session-protocol.md` were prose that a session had
to *remember* to follow, and the 2026-07-11 handoff proved that fails — it went stale and still
listed an already-landed commit as the next step. Now: `git commit` is blocked if pytest is red or a
secret is staged (making "verify by running, not asserting" mechanical — nothing can silently weaken
the temp-71.2 guard); `decisions.md` rejects any edit that removes existing text (append-only was
previously unenforced); `db/queries.sql` rejects lowercase SQL; and the staleness check runs on
every session start instead of when someone remembers. · **Consequences:** commits get slower by the
runtime of the suite (currently ~0.01s). A hook that crashes must fail *open* deliberately, not via
`set -e` — a non-2 exit is a soft error in Claude Code, so a crashing guard silently stops guarding.
Deliberately did **not** port `duly_noted`'s `post-edit-format.sh`: it auto-prettiers `*.md`/`*.json`
and would reformat `db/queries.sql`, which this project forbids — a hook can be actively harmful
when copied across repos with different rules. The siblings' "do not commit the handoff" rule is
also inverted here, because overwrite-plus-git-history *is* our handoff history. · **Refs:**
`.claude/settings.json`, `.claude/hooks/*.sh`, `.claude/skills/handoff/SKILL.md`.

## 2026-07-13 — patient.sex is optional; declining to state sex is a clean value
**Decision:** Remove `patient.sex` from `REQUIRED` in `LocalValidator`. An undeclared sex — absent,
empty, `unknown`, `other`, or an explicit **"prefer not to say"** — produces **no issue at any
severity**, and it *suppresses* the sex-restricted-code rule entirely. The rule fires only on a
definitely-stated `M`/`F`, after normalisation (`"m"`, `"male"`, `" M "` → `M`). A value we cannot
map at all (e.g. `"42"`) is `info`, with the remediation aimed at the ingest mapping rather than the
patient. · **Status:** accepted · **Why:** two reasons, one ethical and one about correctness.
(1) A patient must be able to opt out of stating sex without the pipeline recording a defect against
their record. Previously `sex` was in `REQUIRED`, so declining to answer scored **`critical` —
"Required field is missing or empty"** — the exact same severity as `SpO2 = 105`. The system was
calling a legitimate human answer a near-certain data-entry error. Modelling against FHIR
`AdministrativeGender` (`male | female | other | unknown`, plus asked-but-declined as a distinct
data-absent reason) is both the humane choice and the standards-correct one. (2) With no asserted
sex there is nothing for a sex-restricted diagnosis code to contradict, so firing the rule would be
asserting a contradiction we cannot actually derive. Silence is the correct output, not a guess.
· **Consequences:** the original Task-2 code from the plan compared `sex == "M"` against a `.upper()`ed
diagnosis code — an asymmetry that made a `"sex": "m"` record with a pregnancy code come back
`status: pass`, `issue_count: 0`, `domain: clean`, **not escalated**. A silent false negative in the
engine the whole presentation argues is the *trustworthy* one; caught by `/code-review`, fixed here,
and now pinned by tests. Severity choices follow the CLAUDE.md ladder (severity = plausibility of the
datum): an unmappable sex string is a plausible value that is merely poorly encoded, so `info` — the
same shape as the existing wrong-case `code_system` rule. Note a pre-existing quirk this makes more
visible: **any** issue, including an `info`, sets `status: "fail"`, so an unmappable sex reads as a
failed record. Left as-is; revisit if it muddies the demo. · **Refs:** `app/validator.py`
(`SEX_UNDECLARED`, `SEX_SYNONYMS`, `_normalise_sex`, section 6), `tests/test_validator_sex_codes.py`,
plan Task 2.

## 2026-07-13 — `/validate` and `load_results.py` must persist the same thing
**Decision:** `save_reports_bulk` now takes `(report, source_system, routing, payload)` tuples, and
both writer paths — `POST /validate` and `load_results.py` (fixtures *and* bulk) — persist routing +
`payload_json`. `payload_json` added to `validation_runs`. · **Status:** accepted · **Why:** the two
writers had silently drifted. `/validate` routed each record; the loader did not — so **every row in
the demo DB had `routing_domain = NULL`**, and `/stats` + the domain SQL analytics reported nothing
by domain. Since the loader is how records actually reach the DB in bulk, the entire Phase-2 routing
feature was invisible in the data it was built to analyse. Nothing failed loudly: the column existed,
the inserts succeeded, the numbers were just empty. · **Consequences:** a schema change needs a real
DB reset — `ensure_tables()` is `create_all`, which creates missing *tables* but **never adds a
column to an existing table**. So the app boots clean and then dies on the first insert with "no such
column". Tests never catch this (they build a fresh DB per test); only the long-lived demo DB does.
After any column addition: `python load_results.py --fixtures` (drops, recreates, reloads). The
general rule: **when two code paths write the same table, a test must pin both** — `payload_json`
alone would have passed while the bulk path still dropped it. · **Refs:** `app/store.py`
(`payload_json`, `save_reports_bulk`), `load_results.py`, `app/main.py`,
`tests/test_store_payload.py::test_bulk_load_persists_payload_and_routing`, plan Task 4.

## 2026-07-13 — the agent batch's inbox is marked, not inferred; findings + marker are one write
**Decision:** `validation_runs` gains an `agent_processed_at` column, stamped once the nightly agent
batch has looked at a record — whether or not it produced findings. `get_noted_records()` takes **no
`batch_date`** and returns noted records where `agent_processed_at IS NULL`. Writing findings and
stamping the marker is a **single function in a single transaction** — `record_agent_result(run_id,
findings, batch_date)`; there is deliberately no separate `save_agent_findings` / `mark_processed`
pair to call in the wrong order. Agent findings go to their own `agent_findings` table, never to
`validation_issues`. · **Status:** accepted · **Why:** the plan's `get_noted_records(batch_date)`
accepted a `batch_date` its body never used — an accepted-and-ignored parameter, the same shape of
silent drift as the Task-4 loader that took routing data and dropped it. Three ways to scope the
batch were considered: (a) infer "unprocessed" from *absence of findings* — but a record the agents
**clear** writes zero findings, so it would be re-read and re-paid-for on every future run, forever;
(b) filter on `run_at`'s date — semantically real, but a demo footgun (load fixtures Monday, run the
batch Tuesday, get a silently empty worklist and no error); (c) an explicit marker — chosen. A record
is in the inbox because we have *not looked at it*, which is a fact about our processing, not a fact
we can derive from the data. Adding a `batch_date` column to `validation_runs` was rejected as
redundant: `run_at` already holds that date, and two copies of one fact can disagree. · **Consequences:**
the two-call shape (`save_findings` then `mark_processed`) has two silent failure modes and both are
now unreachable by construction: die between the calls and the record is re-read next run and its
findings written a **second** time (the worklist and the SQL analytics double-count); stamp first and
fail the write and the record leaves the inbox **forever** with its defects unreported. One
transaction, so neither is possible — `test_findings_and_marker_commit_together` pins the rollback.
A cleared record is recorded as `record_agent_result(run_id, [], batch_date)` — zero findings, still
stamped. An unknown `run_id` raises rather than silently stamping nothing. `WORKLIST_DOMAIN_ORDER`
must list **every** domain `router.py` emits (`admin` was missing): an unlisted domain sorts silently
to the bottom of the worklist — the Task-3 labs skew again, invisible until someone reads the
analytics. `get_worklist` orders by `finding_id` so findings tied on (domain, severity) don't
reshuffle between identical runs. Schema change ⇒ DB reset: `python load_results.py --fixtures` (run
2026-07-13). Note the batch inbox is **empty until Task 11** — no current fixture carries a
`clinical_note`; Task 11 adds them. · **Refs:** `app/store.py` (`agent_findings`,
`agent_processed_at`, `record_agent_result`, `get_noted_records`, `get_worklist`,
`WORKLIST_DOMAIN_ORDER`), `tests/test_store_findings.py`, plan Task 5 (deviates: no `batch_date` on
`get_noted_records`; `save_agent_findings` + `mark_processed` collapsed into `record_agent_result`).

## 2026-07-13 — Lyzr Starter plan ($19/mo, 2,000 credits): buy evidence, not a new architecture
**Decision:** upgrade to Lyzr **Starter** (2,000 credits/mo). **The architecture does not change.**
Record/replay (Task 8) and the credit ledger (Task 7) are **kept**; the ledger's hard cap is raised
(free-tier value was ~2 live calls) rather than removed. Prompts stay in our repo (`specialists.py`),
**not** in Lyzr's UI, even though Starter's 15-agent allowance now makes two deployed agents possible.
A new **Task 13** is added: run the rules-vs-LLM comparison **N times** over the fixtures and report
the LLM's miss rate. · **Status:** accepted · **Why:** a batch run is array-in/array-out — ≤2 calls,
so ~2 credits. The free tier's 20 credits/mo = ~10 total runs: enough to build and demo once, with
**zero** room to iterate a prompt or rehearse. Starter = ~1,000 runs, so the constraint stops binding.
The thing that buys is **evidence for the thesis**: CLAUDE.md's argument is that the LLM *silently
drops issues the script catches*, and on the free tier that comparison was affordable roughly **once**
— a single unrepeatable sample, and if the agent had a good night there'd be no finding to present.
Run it N times and the claim becomes a number ("the agent missed the SpO2=105 critical in X of N
runs"), which is the strongest slide in the deck. Second: a live demo can now be rehearsed without
burning the month's budget. · **Consequences:** record/replay is **not** a credit workaround and does
not get ripped out — network-free tests are deterministic, fast and free in CI, which is correct
regardless of budget; what changes is that recordings can now be **regenerated** freely instead of
hoarded. The ledger stays for the same reason: a hard spend-gate in front of LLM calls is a genuine
engineering artifact and a portfolio talking point — deleting it to save an hour would delete the
talking point. Prompts stay in git because version-controlled, diffable prompts are the better
engineering story and they survive Lyzr going away; the 15-agent allowance changes this from a
constraint into a *choice*, and the choice is still repo-side. Starter also adds 7-day trace logs —
screenshot them for the presentation. Note the free tier remained *sufficient* to ship: $19 bought
iteration headroom, demo safety and quantified evidence, not a feature otherwise unshippable.
· **Refs:** plan Tasks 7, 8, 12; new Task 13; `docs/phase-checklist.md`; supersedes the handoff's
"Lyzr deployment shape" open decision (resolved: one generic agent, prompts in `specialists.py`).

## 2026-07-13 — the evidence guard is a *fabrication* guard, and every drop is counted
**Decision:** `app/agents/schema.py` keeps a finding only if it is well-formed *and* its `evidence`
is a verbatim quote of the note. Three things beyond the plan: (1) `partition_findings` returns
`(kept, dropped)` with **all** applicable reasons per drop — nothing is silently discarded;
(2) `is_valid_finding` validates **values**, not just key-presence (severity/domain against allowed
sets, required fields non-empty); (3) evidence must clear `MIN_EVIDENCE_CHARS = 6`, and `_norm` folds
Unicode punctuation as well as case/whitespace. The guard is **renamed in our own docs from an
"injection guard" to a fabrication guard**. · **Status:** accepted · **Why:** the plan's version had
three holes. **The verbatim check was trivially defeatable** — any substring counted, so a model
could "ground" a wholly invented finding on `"a"` or `"the"`, which appear in every note; a length
floor makes the guard mean something (6 blocks the degenerate case while keeping genuinely short
clinical quotes: "A1c 6.9", "room air", "SpO2 98%"). **Key-presence is not validity** — `severity:
"banana"` passed, and `store.WORKLIST_DOMAIN_ORDER` sorts an unknown domain *silently last*, so junk
would reach the DB and sink in the worklist unseen (Task 3's labs skew, again). **And `keep_grounded`
threw the drops away** — but the drop rate IS the presentation's evidence, so it must be countable.
Reasons are collected in full rather than first-match-wins: if `malformed` masked
`evidence_not_in_note`, the hallucination rate we report would be undercounted by whatever share of
bad findings also happened to be malformed. · **Consequences:** **Unicode folding protects the
headline number.** Models re-type quotes with typographic punctuation (note has `patient's` U+0027,
model returns `patient’s` U+2019). Unfolded, the substring check fails and a *real* finding is
dropped as `evidence_not_in_note` — a **false hallucination inflating the exact statistic the thesis
rests on**. Two limits are now pinned by `test_LIMIT_*` tests so a future session cannot mistake them
for bugs: **(a) this is not an injection defence** — an attack carried *in the note* is, by
construction, a verbatim quote of the note, so the guard keeps it (beating that needs ingest-time
sanitisation, which we don't do); **(b) verbatim ≠ faithful** — the note says "Denies dysuria" and a
model can claim the patient *has* it while citing "dysuria", a real substring. The guard proves the
quote is real, not that it supports the claim. **The mitigation for (b) is that a human adjudicates
the worklist — which is precisely why the output is a worklist and not an auto-correction.** Both are
presentation material (see `docs/for-review.md`), not embarrassments. · **Refs:** `app/agents/schema.py`,
`tests/test_agents_schema.py`, plan Task 6 (deviates: `partition_findings`, value validation,
`MIN_EVIDENCE_CHARS`, Unicode fold, and the guard's honest name).

## 2026-07-13 — the credit ledger fails closed, buckets by month, and holds a lock

**Decision:** `app/agents/ledger.py` caps live Lyzr calls against a **per-calendar-month** budget
(`{"months": {"2026-07": 12}}`), read from `LYZR_CREDIT_BUDGET` with a **free-tier-safe default of
15**. Four deviations from plan Task 7: (1) monthly buckets, not a lifetime counter; (2) budget from
the environment, not a hardcoded argument; (3) writes are atomic (temp file + `os.replace`, file and
directory both fsynced) and the whole read-modify-write is held under an `fcntl.flock`; (4) an
unreadable or non-integer ledger raises **`LedgerCorrupt`** rather than being read as zero. ·
**Status:** accepted · **Why:** **a lifetime counter goes out of sync with the vendor** — Lyzr's
allowance resets monthly, so a cumulative cap eventually blocks a fresh billing month while Lyzr is
happily serving; buckets also preserve "we made N live calls in July", which is the spend record.
**The default is 15, not the paid allowance (2,000) or a fraction of it, on purpose:** if the $19/mo
Starter subscription lapses, the number that is already in force is survivable on the 20-credit free
tier, and nobody has to remember to lower it. **Failing closed is the ledger's whole job** — this is
the only gate in front of real money, and a ledger that swallows a parse error and reports "0 spent"
hands the entire budget back on every corrupt read, silently, while being trusted. That is worse than
having no ledger. · **Consequences:** three of these came out of `/code-review` and one was proven by
a test that *failed before the fix*: **`spend()` is a read-modify-write, so without the lock two
processes both read 14/15, both decide there is room, and both write 15 — two credits spent, one
recorded.** The concurrency test reds without `flock`. Also pinned: **`spend(1.5)` used to pass the
`n < 1` guard, write `1.5` to disk, and brick the ledger** — every subsequent read would raise
`LedgerCorrupt` and lock out all live calls until a human hand-edited the file; and **an unvalidated
`month` key silently doubled the cap** (`"2026-7"` writes a different bucket than `current_month()`
reads, each with a full fresh budget). The ledger file is **gitignored under both names**
(`.lyzr_ledger.json`, the `LYZR_LEDGER_PATH` default, and `ledger.json`): it is machine state, and a
committed copy would let a stale checkout resurrect an old spend count. **`fcntl` is POSIX-only** —
fine on macOS and Render, would need revisiting on Windows. · **Refs:** `app/agents/ledger.py`,
`tests/test_agents_ledger.py`, plan Task 7 (deviates: monthly buckets, env budget, atomic write +
lock, explicit fail-closed).

## 2026-07-13 — a recording belongs to the question that produced it, and live mode fails closed

**Decision:** `app/agents/transport.py` is the only code in the project that talks to Lyzr. Answers are
saved to disk and replayed for free, and a recording is filed under the specialist **plus a
fingerprint (truncated SHA-256) of the exact message we sent** — not under the specialist alone, as
plan Task 8 had it. `Replayer.response_for` therefore takes `(specialist, message)`, one argument more
than the plan's interface. Live mode requires a `CreditLedger` and an `agent_id` or it **refuses**;
`ledger=None` no longer means "no cap". The HTTP call gets a 60s timeout and raises `LiveCallFailed`
carrying the **status code**. Recordings are **committed**, and their location is overridable via
`LYZR_RECORDINGS_DIR`. · **Status:** accepted · **Why:** **filing by specialist alone serves the wrong
patient's answer, silently.** One file per specialist, overwritten each live run, means a replay over
records that were never recorded returns whatever the last run produced. Every finding must quote *its
own* note (Task 6), so those findings would then be dropped as fabricated — **the drop rate on the
presentation slide would be measuring our own bug, not the model's honesty.** With a fingerprint, an
unrecorded input raises `FileNotFoundError` and says so. The stored question is also **compared on
read**: the fingerprint picks the file, the question inside proves it is the right one, so the
guarantee does not rest on a 12-character filename that can be hand-copied or collide. **`ledger=None`
meaning unlimited is the same fail-open hole the ledger exists to close** — a stray `EHR_ENGINE=lyzr`
and a loop is all it takes. · **Consequences:** **`message` must be a pure function of the records** —
a timestamp, a uuid or an unsorted dict inside `build_message` (Task 9) would change the fingerprint on
every run, so no replay would ever hit and a live batch would re-pay for records it already recorded.
This is now stated in `get_response`'s docstring and must be pinned by a determinism test in Task 9.
**The credit is charged BEFORE the call**, so a Lyzr 500 still costs one — deliberate, because charging
afterwards lets a runaway loop drain the budget before the ledger hears about it; losing one credit to
their 500 is the cheaper mistake, and the docstring says so to stop a well-meaning refactor reordering
it. Errors never interpolate the `Request` (urllib puts headers, and therefore the **API key**, into
some exceptions — the key was rotated after an exposure once already); the status code carries no
secret and is included, because at one credit per retry "the call failed" cannot distinguish a wrong
key (401) from a wrong agent id (404) from a rate limit (429). Crash-safe writing is now shared by the
ledger and the recordings in `app/agents/_fileio.py`. · **Refs:** `app/agents/transport.py`,
`app/agents/_fileio.py`, `tests/test_agents_transport.py`, plan Task 8 (deviates: fingerprinted
recording key + stored-question check, ledger and agent_id required in live mode, HTTP timeout +
status code, `LYZR_RECORDINGS_DIR`).

## 2026-07-13 — an unreadable reply is not a clean record; every field we demand, we define

**Decision:** `app/agents/specialists.py` defines the two agents (clinical, identity), each seeing
only its own slice of the record. Five deviations from plan Task 9: (1) **`parse_findings` RAISES
`ResponseUnparseable`** on a reply it cannot read, instead of returning `[]`; (2) the message is
**deterministic** — records sorted by `run_id`, `json.dumps(sort_keys=True)`, prompts built from
constants; (3) the contract **enumerates every allowed value** (domains and severities generated from
`schema.VALID_DOMAINS`/`VALID_SEVERITIES` so prompt and guard cannot drift apart) and defines every
field it asks for; (4) findings are attributed by **`record_id`**, which falls back to `run-<run_id>`
when a payload has no `encounter_id`; (5) slices are `copy.deepcopy`, not a JSON round-trip. ·
**Status:** accepted · **Why:** **returning `[]` for a broken reply makes a broken agent look like a
perfect one.** "The agent returned garbage" and "the agent found nothing wrong" would be the same
value, so an agent that had failed completely would score as never raising a false finding and never
missing one — and Task 13's miss rate, the number this whole project argues from, would be measuring
silence. **An undefined field is a field the model guesses at.** We demanded a `domain` and never said
which four were legal; a sensible guess ("vitals") is rejected by `is_valid_finding`, tallied as
MALFORMED, and reported as the model's unreliability. **That is our prompt's defect scored as the
model's — the Task-6 Unicode bug wearing a different hat, corrupting the same headline number.** The
prompt is now generated from the guard's own constants, so the two cannot drift. · **Consequences:**
**`parse_findings` tolerates how models WRAP an answer and refuses how they FAIL.** Code fences, a
preamble ("Here are the findings:"), a bare list — all parsed, because throwing a *correct* answer away
as unreadable would inflate the LLM-failure rate **in our own favour**, which is worse than useless: it
is a number we would have to retract. Only a reply with no findings list anywhere raises. **A record
with no `encounter_id` used to be unattributable**: the batch discards findings whose id was not in the
batch, so every finding about that record would vanish *while the record was still stamped processed* —
gone from the inbox forever, with its defects unreported. `run-<run_id>` cannot be missing. The
JSON-round-trip deep copy would have **raised TypeError on a `Decimal`**, which is exactly what Postgres
returns for a NUMERIC column — a crash waiting on the deploy target. Error messages truncate the reply
to 200 chars: a model's 4KB apology echoes the chart back, and that should not land whole in a log or a
screenshot. · **Refs:** `app/agents/specialists.py`, `tests/test_agents_specialists.py`, plan Task 9
(deviates: raise-not-empty, determinism, enumerated contract, `record_id` fallback, deepcopy).

## 2026-07-13 — the batch is all-or-nothing, and a cleared record is still a reviewed record

**Decision:** `app/agents/batch.py` runs the agents: inbox → one call per specialist → attribute →
guard → persist → stamp. Five deviations from plan Task 10: (1) **every record is stamped, including
ones the agents cleared** (the plan only wrote when a record HAD findings); (2) findings from all
specialists for one record are written in **one call per record**, not one per specialist; (3) an
unreadable reply **aborts the whole batch** (`BatchAborted`) — nothing written, nothing stamped, and
the offending recording is **quarantined** to `.rejected`; (4) the batch returns `{"worklist",
"dropped", "counts"}`, not a bare list; (5) `domain`/`owner` are stamped from the specialist **before**
the guard runs. The batch validates `batch_date` (`YYYY-MM-DD`) and holds an exclusive lock for the
whole run. · **Status:** accepted · **Why:** **stamping only records with findings means every clean
record is re-read — and in live mode re-paid for — on every run, forever.** Zero findings is an answer,
not an absence of one (this is the Task-5 marker argument, and the plan's batch quietly broke it).
**Writing per specialist leaves a record half-reviewed:** a crash between the clinical call and the
identity call stamps the record with only half its review, and because stamping removes it from the
inbox, no future run ever revisits it. Same reasoning for aborting on an unreadable reply: the only
alternatives are to persist half a review or to guess what the model meant. · **Consequences:** **A
junk reply, once recorded, would wedge replay permanently.** The transport records a reply BEFORE
anything parses it (deliberately — it is an honest record of what the agent said), so a live call that
returns prose leaves a junk recording that every future offline run replays and fails on, with nothing
saying why. The batch now moves it to `<name>.rejected`: out of the replay path, still on disk as
evidence. `BatchAborted.credits_spent` carries what the failed run cost — after the raise, nobody can
reconstruct it, and **"the LLM cost N credits and returned unusable output in M of N runs" is the
sentence Task 13 exists to produce.** The specialist, not the model, owns `domain`: we overwrite it
anyway, so letting `is_valid_finding` reject a finding for a bad domain first would mark the model down
on a field we discard — **inflating the very drop rate the presentation reports.** An empty inbox
returns **the day's existing worklist**, not `[]`: a second run on the same date would otherwise tell a
demo audience the pipeline had lost their findings. `batch_date` is validated because a typo
(`"2026-7-13"`) files findings under a key nothing queries **while still stamping the records** — they
would be gone from the inbox and invisible to every query. The whole run holds an `flock` (shared with
the ledger, in `_fileio.exclusive_lock`): two overlapping runs would both read the same unstamped
inbox and write every finding twice. · **Refs:** `app/agents/batch.py`, `tests/test_agents_batch.py`,
`app/agents/_fileio.py`, plan Task 10 (deviates: stamp-always, per-record write, abort + quarantine,
counted result, stamp-before-guard).

## 2026-07-14 — Task 11: demo fixtures are tests/fixtures data; recordings are generated, never hand-authored

**Decision:** the two demo payloads live at `tests/fixtures/payloads/payload_wrong_patient_note.json`
and `payload_note_clean.json` (tracked; `/payloads/` stays gitignored). The wow note was rewritten to a
**hypertension follow-up** so its clinical content agrees with the structured I10 diagnosis — only the
identity axis (62-year-old gentleman vs a 34-year-old woman) is wrong. Test recordings are generated at
test time from the real `build_message()` output (`tests/conftest.py::record_reply`); nothing static is
committed under `tests/fixtures/recordings/`. The e2e suite gained a **mixed-batch test**: both records
in one batch, plus a finding that names the clean record while quoting the wow note. Shared test
helpers (`fresh_store` with a restore-reload, `record_reply`, `save_noted_record`) were consolidated
into `tests/conftest.py`. · **Status:** accepted · **Why:** the plan's BPH/tamsulosin note contradicted
the diagnosis list — the clinical prompt *invites* flagging exactly that, so the live run would have
produced findings the pinned "identity only" narrative denies (review CONFIRMED; the live run then
proved the same instinct on the demographics anyway). Fingerprint-keyed recordings make hand-authored
static recordings dead files. The single-record tests could not catch an attach-to-the-wrong-record or
judge-against-the-wrong-note bug — nothing in the suite ran a batch over two coexisting records. The
store-reload helper existed in four drifting copies, three of which left `app.store` bound to a deleted
temp DB for later-collected tests. · **Consequences:** the clean test pins the full counts dict
(`records: 1` is load-bearing — without it the test passes vacuously on an empty inbox, verified by
experiment). `ingest()` routes via `route()` + `source_system` so test rows match production shape. ·
**Refs:** `tests/test_e2e_wow_catch.py`, `tests/conftest.py`, plan Task 11 (deviates: fixture location,
generated recordings, mixed batch).

## 2026-07-14 — Task 12: the credit gate lives inside LyzrValidator, not in its callers

**Decision:** `LyzrValidator.validate` itself charges the ledger — free config checks first, then
`spend(1)`, then the network via `transport.call_lyzr_live` (one Lyzr transport, with timeout and
key-scrubbed errors). `app/main.py` carries no spend gate; it translates `BudgetExceeded` → HTTP 429
and `LedgerCorrupt` → 503. New CLI `python -m app.agents --date … --mode replay|live` prints the whole
batch result and turns deliberate refusals into one-line `batch refused: …` exits. `ledger_path()`
lives beside the ledger; `*.lock` sidecars are gitignored; `batch_date` is validated as a real calendar
date (regex + strptime). The batch agent id comes from `LYZR_BATCH_AGENT_ID`, falling back to
`LYZR_AGENT_ID` (the Phase-1 validator agent, which has its own baked-in prompt). · **Status:**
accepted · **Why:** review CONFIRMED that a caller-side gate left `load_results.py --engine lyzr`
completely unmetered — one live call per record of the bulk dataset, the exact drain the ledger exists
to prevent — and that charging before the config check let a mis-deployed server (engine set, key
missing) brick a month's budget on requests that never touched Lyzr. Verified by running: bulk load
with budget 0 dies on `BudgetExceeded` before any I/O. · **Consequences:** every constructor of
`LyzrValidator` is gated by construction; guard tests use fake creds + an unroutable localhost URL so
no state of the code lets the suite reach Lyzr (a real credit was spent learning this — see the ledger
entry below). · **Refs:** `app/validator.py`, `app/main.py`, `app/agents/__main__.py`,
`tests/test_engine_guard.py`, plan Task 12 (deviates: gate location, HTTP translation, env fallback).

## 2026-07-14 — first live run: the JSON-escape rule earns its place in the contract

**Decision:** one generic passthrough agent ("EHR Batch Specialist", `anthropic/claude-sonnet-5`,
temperature 0, no Lyzr features, Memory off) serves both specialists; the role/instructions in Lyzr are
a three-sentence "follow the message, return only JSON" shell because the real prompt rides inside
every message. `_CONTRACT` gained: *never put an unescaped double-quote inside a string value*. The
first live run's quarantined identity reply (`identity-c5a33ce664c6.json.rejected`) is **committed as
evidence**, alongside the two good recordings from the second run. · **Status:** accepted · **Why:**
the very first live reply broke JSON by quoting ("gentleman") inside a string — the model caught the
wrong-patient content and lost the whole reply to a quote mark. Temperature 0 makes that failure
deterministic: retrying without the contract fix would buy the identical failure. The abort machinery
worked exactly as designed (nothing written, records kept in the inbox, junk quarantined, spend
recorded: `BatchAborted.credits_spent`). · **Consequences:** Task 13 has its first real data point —
1 of 2 live runs returned unusable output, 2 credits paid for it. The live worklist shows the wow
record caught **four ways** (both specialists, sex + age each) — richer than the authored test
narrative, exactly as the Task-11 review predicted. Ledger and Lyzr agree: 4 credits spent 2026-07.
**Open:** the Studio sidebar shows a 20-credit monthly quota resetting Aug 11 despite the 2026-07-13
Starter upgrade — verify billing before sizing Task 13 (OQ #6). · **Refs:**
`app/agents/specialists.py` (`_CONTRACT`), `app/agents/recordings/`, `docs/for-review.md`.

## 2026-07-17 — Task 13 live comparison: order alone changes the LLM's answer; rules never move

**Decision:** the rules-vs-LLM comparison ran live 2026-07-16 at N=5 tries over the same 5 fixtures,
one comparison message per try (1 credit each), with **record order inside the message as the only
variable** — a fixed rotation, so any drift between tries is attributable to ordering, not content.
All 5 replies were usable (the Task-12 JSON-escape contract rule held; 0 quarantined). Results, per
the SQL over the persisted grades: rules returned the identical 15/15 problems every try; the LLM
gave **a different answer every try** — 1 silent miss (the `metadata.extract_timestamp` warning,
dropped in 1/5), 5 misgrades (the missing facility NPI, a **critical**, downgraded in 2/5; the
malformed diagnosis code, the impossible BP, and the missing DOB once each), and 11 invented
problems (`encounter_id` flagged on 4 rule-clean records in 2 tries; `patient.age` flagged once on
the certified-clean record). Replay reproduces the whole run byte-for-byte from the committed
recordings (47d2868). · **Status:** accepted · **Why:** this is the thesis-as-evidence slide — the
miss rate was the point of the task, and the ordering-sensitivity result is stronger than the
planned "missed X in N runs" framing because temp-0 determinism was expected to make tries
identical, and it did not survive a reordered prompt. · **Consequences:** the presentation sentence
is now measured, not asserted: "same 5 records, five tries — the rules: identical 15/15 every time;
the AI: a different answer every time the order changed." One extra credit was lost to a 60s
timeout before the run; the timeout is now configurable via `.env` and a junk value refuses before
the charge (549c2c1). Ledger 10/15 spent; Lyzr sidebar ≈8.8 credits left this cycle. ·
**Refs:** `app/agents/recordings/` (5 comparison recordings), `db/queries.sql` (miss rate,
scorecard, confusion, reliability — 3910cb1), `docs/for-review.md` (Half 2 numbers), OQ #4/#6.

## 2026-07-19 — Month-end auditor agent approved; presentation is a recorded video built around three replay demos

**Decision:** two coupled scope decisions, both Andy-approved 2026-07-18/19. (1) The final
presentation is a **15-minute recorded video** (slot moved to Tue Jul 21 9:30 EST; Andy may be
unable to attend and proposed a YouTube recording): HTML deck published as a private Artifact,
script written in Andy's measured voice (profile from his sent mail), three screen-recorded demo
segments run entirely from committed replay recordings at zero credit cost, story-first structure
with Mahima's four required headings (Project Objective / Live Project Demo / Key Outcomes / Way
Forward) verbatim on slides. (2) Build the **month-end auditor agent now** — Phase 3 of the
original capstone pitch, delivered instead of promised: one Lyzr call per month over (a) the
month's SQL aggregates and (b) the full synthetic note corpus, reporting only patterns a GROUP BY
cannot express, grounded by the same verbatim-evidence guard, graded against a **planted answer
key** in a committed deterministic generator (four plants: unit-conversion root cause, copy-paste
propagation, gender tone bias, race-correlated missingness — the last planted SQL-countable on
purpose, so the deterministic/LLM split is demonstrated honestly). · **Status:** accepted ·
**Why:** the auditor is the one agentic addition that strengthens the thesis rather than
contradicting it — SQL gets first crack at everything, the agent is credited only for judgment
over aggregates and semantics in prose (root causes, paraphrased duplication, documentation-bias
tone) that rules genuinely cannot reach; bias detection makes that split vivid and is credible to
a healthcare audience. Con, recorded: presenting Phase 3 as built admits it was late; building it
now spends deadline slack. · **Consequences:** hard fallback is binding — if the auditor is not
graded and green by Sun morning Jul 19–20, it drops to Way Forward and the deck ships with the
two-demo map; the presentation never waits on the agent. Live budget ≤2 credits (≈8.8 remain).
Bias framing rule: the auditor flags documentation bias in synthetic data with a known answer
key — it does not diagnose people or accuse clinicians. · **Refs:**
`docs/superpowers/specs/2026-07-18-month-end-auditor-design.md` (0494f7f),
`docs/superpowers/plans/2026-07-18-month-end-auditor.md` (80cb847), `docs/for-review.md`,
Mahima's Jul 1 + Jul 16 emails (requirements + reschedule).

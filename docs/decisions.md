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

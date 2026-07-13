# Phase Checklist — Phase 2 (in progress)

Live tracker for the current phase. Tick a box only when **verified by running it** (not assumed).

## Done this phase
- [x] `store.py` → SQLAlchemy Core, env-var-driven DB URL switching
- [x] Four routing columns on `validation_runs` (routing_domain, escalated, routing_reason, llm_summary)
- [x] `app/router.py` — field→domain map, priority-ordered primary domain, escalate on any critical
- [x] `main.py` wires routing into `/validate` — *verified 2026-07-08: POST returns populated `routing`*
- [x] **Server boots cleanly** — *verified 2026-07-08: uvicorn boot line, `/health` ok, `/validate`
      returns routing fields, `/stats` returns domain breakdown* (fixed a `DB_PATH` import break +
      dead router; split `init_db` from non-destructive `ensure_tables`)

## Remaining (build order)
- [ ] **Test suite** — pytest over the 5 fixtures pinning validator output; include a regression
      guard on the temp-71.2°F critical (protect the demo finding). *(merged practice — new)*
  - [x] Task 1: pytest harness + temp-71.2 regression guard — *verified 2026-07-13: 2 passed; guard
        proven to bite (widening the temp hard-bound flips critical→warning and reds the test).
        Fixtures tracked at `tests/fixtures/payloads/` so a fresh clone runs green.*
  - [x] Task 2: sex-restricted diagnosis-code rule — *verified 2026-07-13: fires on a definite M/F
        (after normalising "m"/"male"); an undeclared sex ("prefer not to say", unknown, other,
        absent) yields **no issue at any severity** and suppresses the rule. `patient.sex` dropped
        from REQUIRED — declining to answer was scoring `critical`. See `docs/decisions.md`.*
  - [x] Task 3: `labs[]` + ordered-vs-resulted rule — *verified 2026-07-13: warning on either
        mismatch; lab defects now route to **clinical**, not the `admin` catch-all (would have
        skewed the domain breakdown in the SQL analytics).*
  - [x] Task 4: persist raw `payload_json` per run — *verified 2026-07-13: 30 passed; DB reloaded and
        inspected. Also fixed `load_results.py`, which never routed — every row had
        `routing_domain = NULL`, so `/stats` + the domain analytics were empty. Both writers
        (`/validate` and the loader) now persist routing + payload. See `docs/decisions.md`.*
  - [x] Task 5: `agent_findings` table + noted-records/worklist queries — *verified 2026-07-13:
        41 passed; DB reset + fixtures reloaded (new `agent_processed_at` column). Deviates from
        the plan: `get_noted_records()` takes no `batch_date` (the plan's body ignored it); findings
        + processed-marker are written in ONE transaction via `record_agent_result` so the batch
        cannot lose or double-count findings. Inbox is **empty until Task 11** — no fixture carries
        a `clinical_note` yet. See `docs/decisions.md`.*
  - [x] Task 6: finding schema + verbatim-evidence guard — *verified 2026-07-13: 64 passed; guard
        demonstrated against a real note (hallucinated quote, degenerate `"for"`, and junk severity
        all dropped; a whitespace-reflowed real quote kept). Beyond the plan: `partition_findings`
        returns every drop **with reasons** (the drop rate is the thesis evidence — don't discard
        it); values validated, not just keys; `MIN_EVIDENCE_CHARS=6` (a model could otherwise
        "ground" an invented finding on `"a"`); Unicode punctuation folded (a curly apostrophe would
        otherwise read as a hallucination and **inflate the headline number**). Two limits pinned by
        `test_LIMIT_*`: it is **not** an injection defence, and verbatim ≠ faithful. See
        `docs/decisions.md` + `docs/for-review.md`.*
  - [x] Task 7: credit ledger — *verified 2026-07-13: 82 passed; refusal, persistence-across-
        processes and fail-closed-on-corrupt all demonstrated outside pytest. Deviates from the plan:
        **per-month buckets** (Lyzr's allowance resets monthly; a lifetime counter would block a
        fresh billing month), budget from **`LYZR_CREDIT_BUDGET`** defaulting to **15** (survivable
        on the free tier, so cancelling Starter needs no code change), atomic write + **`fcntl.flock`
        across the read-modify-write** (a race let two spenders past the cap — the test reds without
        the lock), and an unreadable ledger raises **`LedgerCorrupt`** instead of reading as 0 spent.
        Ledger file gitignored under both names. See `docs/decisions.md`.*
  - [ ] Tasks 8–12: see `docs/superpowers/plans/2026-07-09-multi-agent-triage.md`
        (Task 8 = record/replay + live client seam). **Only Task 12 makes a live Lyzr call** —
        Tasks 8–11 run against recorded responses and cost nothing.
  - [ ] **Task 13 (new, 2026-07-13): rules-vs-LLM comparison, N runs.** Run the LLM over the same
        fixtures the rules ran over, N times, and report the miss rate ("the agent missed the
        SpO2=105 critical in X of N runs"). This is the thesis-as-evidence slide, and it is what the
        Lyzr **Starter** upgrade was bought for — the free tier afforded this comparison roughly
        *once*. Keep the credit ledger and record/replay; raise the ledger cap, don't remove it.
        See `docs/decisions.md` (2026-07-13) and OQ #4 (RESOLVED).
- [ ] **LLM escalation** — escalated records only → Lyzr → plain-English summary + cross-field
      contradiction detection (NOT re-validation). Test on fixtures only (credit budget)
- [ ] **Postgres swap + Render deploy** — same SQLAlchemy Core code, switch DB URL (gated by OQ#3)
- [ ] **Minimal web UI** — single HTML page (payload input + results panel + live stats), served by
      FastAPI (gated by OQ#1/#2)

## Per-task loop
decide + note rationale → (test-first where practical) → implement → **run it, observe output vs
expected** → `/code-review` → get approval → commit `[type] …` → push (after approval).

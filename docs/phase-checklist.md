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
- [ ] **LLM escalation** — escalated records only → Lyzr → plain-English summary + cross-field
      contradiction detection (NOT re-validation). Test on fixtures only (credit budget)
- [ ] **Postgres swap + Render deploy** — same SQLAlchemy Core code, switch DB URL (gated by OQ#3)
- [ ] **Minimal web UI** — single HTML page (payload input + results panel + live stats), served by
      FastAPI (gated by OQ#1/#2)

## Per-task loop
decide + note rationale → (test-first where practical) → implement → **run it, observe output vs
expected** → `/code-review` → get approval → commit `[type] …` → push (after approval).

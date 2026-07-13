# Open Questions

Decisions pending info or a checkpoint. Do not build past a blocker until RESOLVED.
**Status key:** OPEN | RESOLVED | DEFERRED. Each has a **Blocks:** line naming gated work.

---

## #1 — Web UI scope (draft — confirm)
**Status:** OPEN
Minimal single HTML page served by FastAPI: payload input, results panel, live stats panel. What
exactly does the stats panel show (clean rate? per-source defect rate? escalation count?), and is it
read-only or does it trigger validation?
**Blocks:** the Phase-2 web UI task.

## #2 — Escalation summary surfacing (draft — confirm)
**Status:** OPEN
`llm_summary` is stored per escalated record. Is it shown in the UI, only in SQL analytics, or both?
**Blocks:** UI results panel; possibly an analytics query.

## #3 — Render deployment timing (draft — confirm)
**Status:** OPEN
Postgres swap + Render deploy is a remaining Phase-2 item. Deploy now or after the UI? (Free Postgres
expires in 30 days — don't start the clock before the demo window.)
**Blocks:** Postgres swap, Render deploy.

---
## Resolved
_(move items here with the resolution + date as they close)_

## #4 — Lyzr plan + deployment shape
**Status:** RESOLVED (2026-07-13)
Upgraded to **Starter** ($19/mo, 2,000 credits) — a batch run costs ~2 credits, so the free tier's
20/mo allowed only ~10 runs total (build + one demo, no prompt iteration, no rehearsal). Starter
allows ~1,000. **Architecture unchanged:** record/replay and the credit ledger are kept (the ledger
cap is *raised*, not removed). Prompts stay in `specialists.py` in git — **one generic agent**, not
two deployed ones — despite Starter's 15-agent allowance, because diffable version-controlled prompts
are the better engineering story and survive Lyzr going away. Rationale in `docs/decisions.md`.
**Was blocking:** Task 12 (needs `agent_id`/key in `.env`). **Still to do:** create the agent in Lyzr
Studio and put `agent_id` + key in `.env` before Task 12.

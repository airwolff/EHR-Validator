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

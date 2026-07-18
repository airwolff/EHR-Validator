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

## #5 — Adjudicator agent (the one genuinely *agentic* addition)
**Status:** DEFERRED (2026-07-13) — revisit only if Tasks 6–13 land with time left before Jul 17.
When the clinical and identity specialists produce **conflicting** findings on the same record, a
third LLM call adjudicates the conflict. This is real cross-agent reasoning and rules genuinely
cannot do it (it is a judgment over two models' disagreement), so it *strengthens* the
deterministic-first thesis rather than contradicting it. Cheap: fires only on conflict, ~1 call.
**The catch:** with 5–7 fixtures the specialists may never actually disagree, so demoing it could
require engineering a conflict — which is a bit staged. Decide with real batch output in hand.
**Blocks:** nothing. Everything through Task 13 proceeds without it.

## #6 — Lyzr plan: still FREE tier; Starter not purchased (new 2026-07-14)
**Status:** RESOLVED (2026-07-14)
Andy confirmed the Starter upgrade was **never purchased** (OQ #4 recorded it as done — it wasn't;
he'll buy it only if needed). The account is the free **20 credits/month** plan, resetting Aug 11.
After this session's live runs the sidebar showed ~**14.8 left**. Sizing that matters for Task 13:
a batch run costs ~2 credits **regardless of how many records are in it** (one message per
specialist), so N comparison runs ≈ 2×N credits — **N=5 runs fits in 10 credits** with ~5 spare.
Buy Starter only if Task 13's design needs more than ~7 runs or prompt iteration goes badly.
**Blocks:** nothing — Task 13 proceeds on the free tier with N sized accordingly.
**Post-run note (2026-07-17):** Task 13 ran N=5 on the free tier; a comparison try turned out to be
**1 credit** (one message), not 2, so the run cost 5 credits (+1 lost to a timeout). ≈8.8 left,
ledger 10/15. Starter never needed.

---
## Resolved
_(move items here with the resolution + date as they close)_

## #4 — Lyzr plan + deployment shape
**Status:** RESOLVED (2026-07-13) — **CORRECTED 2026-07-14: Starter was never actually purchased;
see #6. The architecture decisions below stand; the plan is still free tier, 20/mo.**
Planned upgrade to **Starter** ($19/mo, 2,000 credits) — a batch run costs ~2 credits, so the free
tier's 20/mo allowed only ~10 runs total (build + one demo, no prompt iteration, no rehearsal).
Starter allows ~1,000. **Architecture unchanged:** record/replay and the credit ledger are kept (the ledger
cap is *raised*, not removed). Prompts stay in `specialists.py` in git — **one generic agent**, not
two deployed ones — despite Starter's 15-agent allowance, because diffable version-controlled prompts
are the better engineering story and survive Lyzr going away. Rationale in `docs/decisions.md`.
**Was blocking:** Task 12 (needs `agent_id`/key in `.env`). **Done 2026-07-14:** "EHR Batch
Specialist" created in Lyzr Studio (claude-sonnet-5, temp 0, no features); id in `.env` as
`LYZR_BATCH_AGENT_ID`; first live runs made. **But see #6 — the account looks like it is still on
the free 20-credit plan.**

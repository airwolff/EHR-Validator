# For Review — mentor checkpoints + presentation arguments

Items to raise at a program/mentor checkpoint, and the core arguments to protect in the write-up/demo.
New up top; resolved → bottom.

## Presentation arguments to protect (don't let refactors erode these)
- Deterministic-first: rules are the trusted baseline; LLM only for what rules can't reach.
- The Lyzr **temp 71.2°F miss** is the headline evidence — keep it visible, don't tune it away.
  (A pytest regression guard is planned to lock this behavior in.)
- Severity = plausibility of the datum, not patient survivability.
- **"Multi-agent system with *deterministic orchestration*"** — the correct name for this
  architecture, and the answer to "is any of this actually agentic?" The recognized multi-agent shape
  is all here: **specialist decomposition** (clinical + identity, each with its own input slice and
  prompt — Task 9), a **grounding verifier** over another model's output (`keep_grounded` drops any
  finding whose evidence isn't verbatim in the note — Task 6), **orchestration** (the nightly batch —
  Task 10), and a **hard budget guard** (the credit ledger — Task 7). The one deliberate difference:
  **the control flow is Python, not an LLM.** That is a *defence*, not a limitation — "I did not let a
  language model decide control flow over patient data" is the point, and it's the same argument as
  deterministic-first. Expect to be asked; answer with this, don't apologise.
- **Do NOT add an LLM router** to look more agentic. A deterministic router already picks the domain
  correctly; replacing it with a model would put an LLM exactly where rules *do* reach — the practice
  this whole presentation criticises. It would undermine the thesis to win a buzzword.

## Open / to raise
- Web UI scope + stats-panel contents (see open-questions #1/#2).
- Deploy timing vs the 30-day Postgres clock (open-questions #3).
- **Adjudicator agent (deferred, not dropped — see open-questions #5).** The one genuinely *agentic*
  addition that would strengthen rather than contradict the thesis: when the clinical and identity
  specialists produce **conflicting** findings on the same record, a third call adjudicates. Rules
  cannot do this — it's a judgment over two models' disagreement. Deferred for the Jul-17 window.

## Budget / limits
- Lyzr credits: <track usage here> / **2,000 per month (Starter, $19 — upgraded 2026-07-13).**
  A batch run is ~2 credits (array-in/array-out, ≤2 calls), so ~1,000 runs/mo. The old 20/mo free
  tier allowed ~10 runs *total* — that scarcity is why record/replay + the ledger exist. **Keep both:
  they are engineering artifacts, not credit workarounds.** See `docs/decisions.md` (2026-07-13).

## Resolved
_(move here as items close, with date)_

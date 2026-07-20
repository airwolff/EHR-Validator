# Handoff — EHR Triage Pipeline — 2026-07-19

Read `CLAUDE.md` and `docs/phase-checklist.md` first, then this. See `docs/session-protocol.md`
for how to use/update this file.

## Staleness block (check before trusting)
- **Written:** 2026-07-19 (evening)
- **HEAD at write time:** `0664f5d` (branch `main`; the commit carrying this handoff is one
  `[docs]` commit on top — that alone is not drift)
- **Uncommitted at write time:** clean (this file is the only change, committed right after)
- **Tests:** `python -m pytest -q` → **210 passed in 1.01s** (verified 2026-07-19)
- **Boots?** Yes — `python -c "import app.main"` → `boots` (verified 2026-07-19)
- **Staleness test:** if HEAD moved past the docs commit or `git status -s` differs, trust git +
  code and rewrite this early.
- **Push state:** NOT pushed — GitHub was unreachable from Andy's machine at session end
  (curl to github.com timed out; not a credentials issue). `main` is ~15 ahead of origin;
  Andy pushes first thing. If `git status -sb` still shows ahead, run `git push origin main`.

## Where we are

**The month-end auditor is BUILT, LIVE-RUN, and GRADED: 4/4 planted patterns caught, 0 evidence
dropped, replay reproduces it for 0 credits.** All presentation assets are committed. The
2026-07-18 plan's Tasks 1–11 are done via subagent-driven development, each task reviewed;
per-task record is `.superpowers/sdd/progress.md` (the old Task-13 ledger is archived next to it).

Verified by running this session:
- Auditor code: Tasks 1–6 landed as `e95a2de → bec8eaa` (demographics table, month generator +
  committed answer key, corpus/aggregates reads + Q12, audit module, orchestration + CLI,
  grading + Q13). Suite went 181 → 210, green at every commit.
- **The live-run story (2 credits, ledger now 12/15, 3 remain):** BOTH live audit calls broke
  their own JSON contract identically — unescaped double-quotes where the reply cited the
  AGGREGATES block. The abort path quarantined both; nothing was persisted. Andy chose a
  parse-time repair over a third credit: `_repair_quote_values` (commit `3cc3dde`), TDD-pinned
  against the real quarantined reply. The second recording was then un-quarantined and read
  as-is (`aad5716`) — the recording file itself was never edited. First failed reply is committed
  evidence: `app/agents/recordings/auditor-3bd3022bd092.json.rejected` (commit `e379327`).
- Graded replay (`python -m app.agents.audit --month 2026-06 --mode replay --grade`): 4 patterns
  returned, 4 kept, 0 dropped, 0 credits; grades caught × 4; `invented: 1` (grader term-tie
  footnote: copy_paste_note matched the gender-bias pattern; the templated-note pattern counts
  as "invented"). Re-run reproduces identical output.
- Docs updated with measured numbers (`80bbf75`): phase-checklist Task 14, decisions.md
  2026-07-19 entry (the durable why lives THERE), for-review.md.
- **Presentation assets, all committed:**
  - `docs/presentation/runbook.md` (`663856b`) — three replay demo segments, every command run
    and verified; includes two load-ordering rules that are easy to break (see Gotchas).
  - `docs/presentation/script.md` (`34a88bb`) — 1,876 spoken words = 14.43 min at 130 wpm,
    9 slides, rubric headings as spoken transitions, reviewer-verified facts/voice/timing.
  - `docs/presentation/deck.html` (`0664f5d`) — 9 slides, keyboard nav, dark, self-contained.
    Published as a **private Artifact**: https://claude.ai/code/artifact/ea6fbc13-b3db-4dba-ba2e-7064afb4ed4b
    (republish same file path from a session to update the same URL).
- Local DB state: the runbook's full sequence was left in place — all three demos work in order
  against the current `ehr_triage.db`.

**Deadline:** presentation slot Tue Jul 21, 9:30–11:00 EST; Andy plans a recorded YouTube video;
working assumption remains **recording exists by end of Mon Jul 20**. The Sat-night fallback rule
is MOOT — the auditor made it; Demo 3 is in.

**Final whole-branch review (base `dabda57`, head `0664f5d`): READY WITH FOLLOW-UPS — zero
Critical/Important findings.** All five cross-task checks passed (repair can't corrupt parseable
replies; no schema drift; committed recordings contain no key material; fingerprint fully
deterministic; docs/deck/script numbers mutually consistent). Optional follow-ups (none block
anything) are listed at the end of `.superpowers/sdd/progress.md`: fix the answer-key prose
("~8% baseline", "M031-M040"), add tests for unknown-coalescing / empty-zip / exact-2-hit
grading boundary, use `schema._evidence_reasons` for finer drop reasons, add `<!doctype html>`
to deck.html, scope Q13 by month+mode.

## ► Next step (do this first)

1. **Andy's own pass:** he will rewrite deck + script wording "to make it more human" (his words,
   this session). The HTML is `docs/presentation/deck.html`; keep facts/numbers unchanged — every
   number is measured and cross-verified against the DB.
2. **Record the video** following `docs/presentation/runbook.md` top to bottom (prep section →
   Step A → Segment 1 → Segment 2 → Steps B/C → Segment 3). Replay only; zero credits.

## Dead ends — don't retry

- **Do NOT make a third live audit call.** Both tries failed the same way (JSON escaping), the
  ≤2-call budget is spent, and the graded result already exists via replay of the genuine
  recording. There is nothing a third credit buys.
- **Don't "fix" the failure by editing recordings** — the repair lives in the parser
  (`_repair_quote_values`), tested in `tests/test_audit_module.py`; recordings are evidence and
  stay byte-exact.
- **Don't load the June month before running Demo 1** — `get_noted_records()` has no date
  filter; June's 42 noted records would flood the nightly batch and break replay. Order rules
  are explicit in the runbook ("Known state going in" + Step A).
- **Don't re-run the Task-13 live comparison**; replay reproduces the graded run free (prior
  handoff's rule, still binding).
- The pre-auditor dead-end list is in `docs/decisions.md` 2026-07-14→17 entries.

## Gotchas / carry-forward

- **Wow-record phrasing:** 4 critical findings on E-WOW-01 = **2 identity-domain + 2
  clinical-domain, one underlying wrong-patient defect**. Never say "4 identity criticals" —
  the old shorthand is wrong and the deck/script/runbook all carry the corrected framing.
- **Report month is `2026-06` everywhere**; generator SEED 20260601; regenerating the month is
  byte-identical (`scripts/generate_month.py --out payloads/month`).
- **Grader footnote to say out loud if asked:** grades are 4/4 caught but `invented: 1` — the
  dumb term-grader matched copy_paste_note to the gender-bias pattern on a term tie
  ("identical" + "template" appear in both). It's in decisions.md; the script handles it.
- `LYZR_TIMEOUT_SECONDS=240` is set in `.env` (plan wanted ≥180). Replay needs no key.
- Deck is deliberately dark-only (slides intercut with dark terminal recordings — CSS comment
  explains). Artifact is private until Andy shares it.
- Severity ladder = plausibility of the datum, NOT survivability (`CLAUDE.md`).
- `db/queries.sql` UPPERCASE (hook), `decisions.md` append-only (hook), `payloads/`/`.env`/
  `ehr_triage.db` gitignored, quarantined `.rejected` recordings are committed evidence.
- SDD scratch (briefs/reports/review packages) lives in `.superpowers/sdd/` — gitignored except
  the progress ledger convention; `git clean -fdx` would destroy it (recover from `git log`).

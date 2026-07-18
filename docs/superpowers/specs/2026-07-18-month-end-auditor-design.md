# Month-End Auditor Agent + Final Presentation — Design

Date: 2026-07-18. Status: approved in session, pending Andy's review of this file.
Two deliverables, one deadline: the AiXcelerate recording should exist by end of Mon Jul 20
(live slot Tue Jul 21 9:30–11:00 EST; a second slot may be offered — not confirmed).

## What we're building and why

Two things:

1. **A month-end auditor agent** — the one genuinely agentic addition that strengthens the
   thesis instead of contradicting it. Once a month, an LLM reads the month's SQL aggregates
   plus the raw clinical notes and reports the patterns that SQL cannot express: root causes,
   semantic clusters, and documentation bias. This was Phase 3 of the original capstone pitch
   ("recurring error-pattern recognition") — delivered, not just promised.
2. **The final presentation** — 15-minute recorded video: HTML slide deck (published as a
   private Artifact, presented full-screen in the browser), a read-aloud script in Andy's
   voice (profile from his sent mail: numbers first, short declaratives, comma splices, plain
   verbs, no hype), and screen-recorded demo segments run from committed replay recordings
   at zero credit cost.

The thesis stays the boss: rules for what rules reach, the LLM only for what they can't.
The auditor obeys the same discipline — SQL gets first crack at everything, and the agent
is only credited for what a GROUP BY genuinely can't express.

## Part 1 — the month-end auditor

### Shape

One module, `app/agents/audit.py`, following `batch.py`'s patterns. One Lyzr call per
month-end run (1 credit), charged inside the transport the same way as every other call,
ledger-gated, record/replay via the existing transport. Offline by default (`--mode replay`).

The message contains two things, clearly labeled:
- **The month's SQL aggregates** — the same numbers Q1–Q7 and the new Q12 produce: top
  failing fields, error profile by source system, daily clean-rate trend, field missingness
  by demographic group.
- **The month's note corpus** — every record's `payload_id`, minimal demographics
  (age, sex, race, zip, source_system), and the full `clinical_note`. ~40 records.

Why one call and not several: the corpus is small, one credit is cheap, and the message
visibly IS the two-layer architecture — the deterministic layer's output is the agent's
input. Known risk: one big message is where Task 12/13 found JSON-escape and attention
problems. Mitigation: the same contract rules the batch already uses, and replay means we
only pay live once per graded run.

### Output contract

```json
{"report_month": "YYYY-MM",
 "patterns": [{"name": "...", "severity": "critical|warning|info",
               "evidence": [{"payload_id": "...", "quote": "..."}],
               "hypothesis": "...", "recommended_action": "..."}]}
```

Every `quote` must appear verbatim in that record's own note (reuse the grounding guard's
logic). An ungrounded quote drops, and the drop is counted and reported — same rule as the
batch: every drop is evidence, a silent drop is a lost argument. A pattern whose evidence
all drops, drops whole. Same two known limits as the batch guard (not an injection defence;
verbatim ≠ faithful) — the report is a worklist for a human, not an auto-action.

### The seeded month

A generator script, `scripts/generate_month.py`, committed with a **fixed seed** — the
data itself stays gitignored in `payloads/`, the generator makes the month reproducible.
~40 records across ~3 source systems and a spread of demographics, most records ordinary
(some clean, some carrying routine rule-catchable defects so the month looks real).

Four planted patterns, each with an entry in a committed answer key
(`scripts/audit_answer_key.json`):

1. **Unit-conversion root cause** — from mid-month, source system "MEDITECH" sends `temp_f`
   values that are actually Celsius (~36–39). Rules flag each as implausible; SQL shows the
   spike by system and date; the auditor's job is naming the cause and the fix.
2. **Copy-paste propagation** — one note fragment, lightly paraphrased, across ~5 patients
   of different ages/sexes. Substring matching fails on the paraphrase; semantic similarity
   is the agent's job.
3. **Gender tone bias** — ~4 matched-symptom pairs (same complaint, same vitals): the
   woman's note uses stigmatizing/dismissive language ("anxious", "insists", "poor
   historian"), the man's gets workup language. Invisible to SQL. The headline catch.
4. **Race missingness bias** — records for one race group are missing optional fields
   (e.g. `zip`, labs) at a much higher rate. Planted so SQL **can** count it (new Q12) —
   the auditor is only credited for interpretation and recommended action, not detection.
   This one exists to demonstrate the split honestly on stage.

Bias framing rule for prompt, docs, and slides: the auditor flags **documentation bias in
the data** (language and completeness), synthetic corpus, planted defects, known answer
key — it does not diagnose real people or accuse real clinicians.

### Storage and SQL

- New table (SQLAlchemy Core, same pattern as existing): `record_demographics` —
  `payload_id, age, sex, race, zip, source_system`, filled at load time. Needed because the
  DB stores triage reports today, and Q12 (missingness by demographic) needs demographics
  queryable. Pro: keeps SQL honest (the count really comes from SQL). Con: small schema
  addition this close to the deadline — it's additive only, nothing existing changes.
- New UPPERCASE queries in `db/queries.sql`: **Q12** missingness by demographic group,
  **Q13** auditor scorecard (planted patterns caught / partially caught / missed, from the
  graded answer key), following the Q8–Q11 grading pattern.
- Audit report persisted like other agent results (worklist rows + raw reply recording).

### Grading

Task-13 style: run live once, grade the reply against the answer key (caught / partial /
missed per planted pattern, plus anything invented), persist grades, numbers come from SQL
(Q13), recording committed so the whole thing replays offline for free. A missed planted
pattern is a reported number, not a demo failure — misses are the thesis.

### Tests

Pytest over: generator determinism (same seed → same month), answer-key collision guard
(planted patterns don't overlap in ways that make grading ambiguous), contract parsing,
grounding drops (fabricated quote → dropped and counted), replay end-to-end with a canned
reply, ledger charge on live path only. Pre-commit gate stays green throughout.

## Part 2 — the presentation

Recorded video, 15 min, ~1,900-word script (~130 wpm). Audience: cohort + hiring team +
mentor. Mahima's four required headings appear verbatim as slide labels. Deck: ~14 slides,
HTML, published as a private Artifact. Demo segments: screen-recorded terminal replays,
zero credits. Script: Andy's voice per the saved profile.

| Time | Section | Content |
|------|---------|---------|
| 0:00–1:30 | **Project Objective** | Broken EHR data poisons everything downstream. Objective = the thesis: which tool deserves which job. |
| 1:30–3:00 | Architecture | One diagram: record → two engines, one contract → DB → SQL. "Every night, an agent crew reviews the day's records — no human kicks it off." Control flow is Python on purpose. |
| 3:00–5:30 | **Live Demo 1** — the nightly agent run | Wow record passes every rule; note describes a different person; both specialists catch it, 4 grounded criticals. Where the agent earns its place. |
| 5:30–8:00 | **Live Demo 2** — the rules win theirs | Five-try comparison replay + SQL scorecard. Rules 15/15 identical every try; LLM different every try — 1 silent miss, 5 wrong severities, 11 invented. |
| 8:00–11:00 | **Live Demo 3** — the month-end auditor | Phase 3, delivered. SQL surfaces the symptoms; the auditor names the unit-conversion root cause, the copy-paste spread, and the gender tone bias SQL can never see. Graded against the answer key, replayed offline. |
| 11:00–13:00 | **Key Outcomes** | The measured numbers from all three runs, incl. the slide sentence from for-review.md. Fabrication guard + its two limits, owned out loud. "I did not let a language model decide control flow over patient data." |
| 13:00–14:00 | **Way Forward** | Adjudicator agent, web UI, Postgres deploy, real-corpus caveats. |
| 14:00–15:00 | Close | "I gave each job to the tool that's good at it." Repo pointer. |

Deliverables: the deck (Artifact), `docs/presentation/script.md`, a demo runbook (exact
commands + expected output for the three recorded segments), and a shot list for any stills.

## Timeline and fallback

- **Sat Jul 18 – Sun Jul 19:** build auditor (generator → module → tests → replay green), live run + grading by Sun morning.
- **Sun Jul 19 (rest of day):** build deck + script + runbook.
- **Mon Jul 20:** Andy records segments, assemble, final take, upload.
- **Hard fallback:** if the auditor isn't graded and green by end of Sat, it moves to Way
  Forward as "designed and in progress," Demo 3 is cut, and the deck ships with the
  original two-demo map (times stretch back to the earlier draft). The presentation never
  waits on the agent.

## Constraints that bind this work

Lyzr: ~8.8 credits left; auditor budget ≤2 live runs (1 credit each expected). `.env` key
never committed/echoed. `payloads/`, `.env`, `ehr_triage.db` gitignored. `db/queries.sql`
UPPERCASE. `decisions.md` append-only. Explicit approval before any commit/push.

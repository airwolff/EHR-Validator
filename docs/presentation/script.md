# Presentation script — 15-minute recorded video

Spoken words only, ~130 wpm. Slide numbers match the deck. The three demo hand-offs are
marked as stage directions; the narration under each recording is part of the spoken count.
Mahima's four rubric headings (Project Objective, Live Project Demo, Key Outcomes, Way
Forward) are spoken out loud as section transitions.

---

## [SLIDE 1: Project Objective]

_0:00 → 1:33 cumulative · 201 words_

This project started with one number: 71.2. Early on I sent a record with a body temperature
of 71.2 degrees Fahrenheit through a Claude-based validator, it called the record fine. A
one-line Python rule caught it instantly. That miss set the question for the whole capstone:
which tool deserves which job?

So — the Project Objective. The project is an EHR data-quality triage pipeline. Broken EHR
data poisons everything downstream — billing, analytics, patient safety — so the job is to
catch it at the door. A patient-encounter record comes in as JSON, a validator inspects it, and every defect comes
out structured: field, problem, severity, remediation. The report lands in a database, SQL
runs across all of it to surface trends. One definition up front, it matters for everything
you'll see: severity means plausibility of the datum, not patient survivability. An SpO2
above 100 is critical because it's impossible data, not because anyone's in danger.

The objective, stated as the thesis: for fixed, well-specified rules, a deterministic Python
validator is the correct tool — faster, cheaper, auditable. The LLM exists only for what
rules can't reach: unstructured text, cross-field contradictions, patterns across records.
I'll show both halves with measured numbers.

## [SLIDE 2: Architecture — two engines, one contract]

_1:33 → 3:03 cumulative · 196 words_

One diagram. A record enters, two engines can inspect it: a deterministic Python validator,
and a Lyzr agent running Claude Sonnet at temperature zero. Both return the identical JSON
contract, so one database and one set of SQL queries covers everything. FastAPI serves it,
SQLAlchemy Core keeps the SQL portable — the same code runs on SQLite locally and targets
Postgres for deploy. Every agent call gets recorded, and a replay re-reads the transcript instead of
paying the API again.

The agentic layer sits on top. Every night, an agent crew reviews the day's records — no
human kicks it off. A deterministic router assigns each record a domain, two specialists —
clinical and identity — each read their own slice, and a grounding guard drops any finding
whose quoted evidence isn't verbatim in the note. A credit ledger hard-stops spending at
the monthly budget.

The control flow is Python on purpose. This is a multi-agent system with deterministic
orchestration: specialist decomposition, a verifier over another model's output, an
orchestrator, a budget guard. The one deliberate difference from the buzzword version is
that no language model decides what runs next. That's a defence, not a limitation.

## [SLIDE 3: Live Project Demo — 1 of 3, the nightly agent run]

_3:03 → 5:35 cumulative · 329 words · hand-off to recording at ~3:58_

That brings us to the Live Project Demo. Three recorded segments, all running from committed
replay recordings — zero credits spent on camera, and every run reproduces exactly. Replay
came out of a hard constraint, 20 API credits a month, and turned into an engineering
artifact worth keeping on its own.

Segment one is where the agent earns its place. The record you're about to see, E-WOW-01, is
internally consistent: vitals in range, codes valid, dates sane. The deterministic validator
returns zero issues. It's also wrong. The clinical note describes a 62-year-old gentleman
with hypertension, the structured data says a 34-year-old woman. That's a wrong-patient
note, no field-level rule can see it, you have to read the note against the chart.

> **[DEMO HAND-OFF 1 — cut to the Segment 1 recording: local validator on E-WOW-01 (0
> issues), then `python -m app.agents --date 2026-07-14 --mode replay`. Narrate over it.]**

First the rules: pass, zero issues. Now the nightly batch on the same record. Four findings
come back, all on E-WOW-01, all critical, every one grounded in verbatim note text. Read the
domain column: two say identity, two say clinical. That's not four separate defects. It's
one wrong-patient defect caught from two angles — the identity specialist matched the note
against the demographics, the clinical specialist matched it against the patient context,
independently. The story behind the record: a note copied from a 62-year-old man onto a
34-year-old woman's chart, the exact defect a wrong-patient mix-up produces.

Two more things worth ten seconds here. Every finding carries its evidence — the sex
finding quotes "62-year-old gentleman with a history of hypertension," and the grounding
guard verified that string sits verbatim in the note before anything persisted. The dropped
list is empty, the guard had nothing to throw out. Meanwhile the clean-note control record
cleared with nothing invented on it. And the counts block at the bottom: credits spent,
zero — this is replay, the same run reproduces on any machine with the repo.

That's half one of the thesis. The LLM catches what rules can't reach, the output stays a
worklist for a human, nothing auto-corrects the chart.

## [SLIDE 4: Live Demo 2 of 3 — the rules win theirs]

_5:35 → 7:59 cumulative · 312 words · hand-off to recording at ~6:28_

Segment two is the other half. Same five fixture records, fifteen planted problems, both
engines, five tries. The only thing that changed between tries was the order of the records
in the message. Temperature stayed at zero the whole time.

Each try grades the same way. A planted problem the LLM reports is caught. Reported at the
wrong severity is misgraded. Not reported at all is a silent miss — the dangerous one,
nobody downstream knows it happened. And a reported problem that doesn't exist is a false
alarm, which burns reviewer time. The deterministic validator took the same five tries and
returned the identical 15 out of 15 every time, in milliseconds, for free.

> **[DEMO HAND-OFF 2 — cut to the Segment 2 recording: `python -m app.agents.compare
> --runs 5 --mode replay`, then the Q9 scorecard in sqlite3. Narrate over it.]**

Watch the per-try counts move: caught goes 14, 14, 15, 14, 12. False alarms go 0, 0, 7, 4,
0. Same records, same temperature, different answers. And this scorecard table is SQL over
the persisted grades, not my summary of them.

The second table breaks it out per problem. The worst rows: a missing facility NPI — a
critical, it blocks billing — downgraded in 2 of 5 tries, and a bad extract timestamp
missed outright in one. Every row in that table is a rule the Python validator catches 5
of 5 times.

Here's the sentence this segment exists to earn: I ran both engines over the same 5 records
five times. The rules: identical 15/15, every time. The AI: a different answer every time
the record order changed — 1 silent miss, 5 wrong severities, 11 invented problems, one of
them on a certified-clean record.

The silent miss this time was a bad-timestamp warning, dropped in one try of five. Back in
Phase 1 the miss was that 71.2-degree temperature. Misses move around, that's the point —
you can't patch your way to reliability with a model that answers differently when you
shuffle its input.

## [SLIDE 5: Live Demo 3 of 3 — the month-end auditor]

_7:59 → 10:47 cumulative · 365 words · hand-off to recording at ~9:26_

Segment three is Phase 3 of the original pitch — recurring error-pattern recognition —
delivered, not promised. The specialists read one record at a time. The month-end auditor
reads the whole month at once: 40 synthetic June records, three source systems, four planted
patterns with a committed answer key. The design is one call over the whole month — the SQL
aggregates and the full note corpus go into a single message, so the deterministic layer's
output is literally the agent's input, and one credit covers a live run.

SQL gets first crack at everything. The rules already caught all six MEDITECH records
sending Celsius values in a Fahrenheit field. And query Q12 counts an asymmetry in missing
zip codes: Black patients 8 of 10 missing, 80 percent, against 0 percent for every other
group. SQL counts the asymmetry, the auditor only interprets it.

One framing rule before the recording, stated the way it's written in my decision log: the
auditor flags documentation bias in the data, on a synthetic corpus with a known planted
answer key — it does not diagnose people, and it does not accuse clinicians.

> **[DEMO HAND-OFF 3 — cut to the Segment 3 recording: `python -m app.agents.audit --month
> 2026-06 --mode replay --grade`, then Q12 and Q13 in sqlite3. Narrate over it.]**

Four patterns come back. The auditor names the MEDITECH unit-conversion root cause — not
"temps look wrong" but which system, when it started mid-month, and the Celsius explanation
with the fix. It catches one note fragment copy-pasted across five unrelated patients —
lightly paraphrased, so substring matching fails, semantic similarity is the agent's job.
And it flags the gender pattern: matched-symptom pairs, same complaint, same vitals — the
woman's note says "anxious" and "insists," the man's note gets workup language. A GROUP BY
can never see that. There's the zip-code finding too, and the split stays honest: SQL
counted it, the agent explained it and recommended an action.

Graded against the answer key: 4 of 4 planted patterns caught, 0 evidence dropped, credits
spent zero on replay. One honesty note — two of the plants graded against the same returned
pattern, the grader is a deliberately dumb term-counter anyone can re-run, and I'd rather
report what it says than tune it to look better. It also counted one invented pattern, a
term-tie footnote, not a fabrication.

## [SLIDE 6: Key Outcomes — the measured numbers]

_10:47 → 11:43 cumulative · 121 words_

Key Outcomes. Every number here is measured and comes from SQL over persisted grades or a
committed recording. Demo one: zero rule issues on the wrong-patient record, 4 grounded
critical findings from the agent batch, nothing fabricated. Demo two: rules identical 15
out of 15 across all five tries, the LLM different every try — 1 silent miss, 5 wrong
severities, 11 invented problems. Demo three: 4 of 4 planted month-end patterns caught, 0
evidence dropped, replayed offline for free.

Both halves of the thesis held under measurement. The agent won the jobs that need reading:
the wrong-patient note, the paraphrased copy-paste, the documentation-bias tone. The rules
won every job with a fixed spec, and won it identically every single time.

## [SLIDE 7: Key Outcomes — the guard, and a failure I'm keeping]

_11:43 → 13:11 cumulative · 190 words_

One more outcome, it's the best thesis evidence in the project, I'm telling it as a win.
Both live auditor calls broke their own JSON contract the same way — an unescaped quote
inside a string, right where the reply cited the aggregates block. The deterministic guard
quarantined both replies: nothing corrupted persisted, nothing silently swallowed. Rather
than pay for a third try, I wrote a targeted parse repair, pinned it with tests against the
actual quarantined reply, and recovered the genuine recording without editing it. Total
cost, 2 credits. The deterministic guard caught the LLM breaking its own output contract,
twice, live.

The grounding guard has two limits, both pinned by tests so they're never mistaken for
bugs. It is not an injection defence — an instruction riding inside the note gets cited
verbatim, so the guard keeps it. And verbatim doesn't mean faithful — a model can cite
"dysuria" out of "denies dysuria." That's why the output is a worklist a human adjudicates,
not an auto-correction. The summary of this whole architecture in one line: I did not let a
language model decide control flow over patient data.

## [SLIDE 8: Way Forward]

_13:11 → 13:58 cumulative · 103 words_

Way Forward, four items. An adjudicator agent — when the clinical and identity specialists
conflict on the same record, a third call judges the disagreement, that's a job rules
genuinely can't do; deferred, not dropped. A web UI over the worklist and the trend
queries. The Postgres deploy on Render — the SQLAlchemy Core code is written to run there
unchanged, the free tier's 30-day clock is the only constraint, and synthetic data reloads
fine. And
real-corpus caveats: everything here is synthetic and planted, real notes are messier, so
the grader and the bias framing both need rework before this touches anything real.

## [SLIDE 9: Close]

_13:58 → 14:25 cumulative · 59 words_

Every claim in this talk traces to a committed recording or a SQL query you can re-run.
The rules kept the jobs with fixed specs, the agents took the jobs that need reading, and a
deterministic layer checked the agents' work. I gave each job to the tool that's good at
it. The repo is github.com/airwolff/EHR-Validator. Thanks for watching.

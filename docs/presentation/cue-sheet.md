# Cue sheet — one continuous take

Everything in one place, in order. **Left = what you say** (full wording is in `script.md`).
**Right = what you type.** `SWIPE →` means three-finger swipe to the terminal desktop;
`← SWIPE` means swipe back to the deck.

Each demo is one script — you type `./demo1.sh`, `./demo2.sh`, `./demo3.sh` and real output
streams. The scripts pause between steps; press Enter when you're ready to advance. On camera
the only thing you ever type is `./demoN.sh`, so there's nothing to fumble.

**Before you press record:** `cd docs/presentation`, run `./setup.sh`, confirm it ends with
`SETUP OK`. Do Not Disturb on. Deck full-screen on one desktop, terminal maximized on the
other (already `cd`'d into `docs/presentation`). The scripts find the repo root themselves, so
your working directory doesn't matter beyond typing `./demoN.sh`.

Time marks are cumulative at 140 wpm — a pace check, not a schedule. Requirement is 15:00;
the full script runs 15:44, so don't fall behind early.

---

## SETUP — run this BEFORE recording (off camera)

```
cd docs/presentation
./setup.sh
```

Resets the DB and loads the 7 batch fixtures in the order the replay expects. Ends in
`SETUP OK`. Do **not** load the June month yet — `demo3.sh` does that on camera; loading it now
breaks Demo 1. **Re-run `./setup.sh` before any retake** (demo3 appends June, so a second pass
without a reset double-loads it).

---

## SLIDE 1 — Project Objective  ·  ends ~2:30

**Say:** the 71.2 story — a properly-configured AI validator (temp 0, strict prompt) called a
dead-patient temperature fine; one line of Python caught it. Then the whole-project question:
which jobs go to the AI, which to a plain script. Define severity = *is this number
believable*, not *is the patient in danger*.

**Type:** nothing. Deck only.

---

## SLIDE 2 — Two ways to check a record  ·  ends ~4:39

**Say:** same record in, same shape of answer out. Then the night shift — sorter, two
specialists, the checker that throws out anything an agent can't prove, the budget guard. A
human wrote the order of operations. Then the disclosure: built with Claude Code, decisions
stayed mine, every number came from running it.

**Type:** nothing. Deck only.

---

## SLIDE 3 — Demo 1: the night shift  ·  ends ~7:13

**Say (deck):** the record looks perfect, rules find 0 problems, and it's still wrong — a
62-year-old man's note on a 34-year-old woman's chart. `SWIPE →`

**Type:**
```
./demo1.sh
```
Runs two steps with an Enter-pause between them:
1. the rules on the wrong-patient record → `issue_count: 0`
2. the nightly agent crew on the same record → 4 critical findings

**Point at:** 4 findings, all `critical`, all on `E-WOW-01`. Domain column: `identity` twice,
`clinical` twice — **one** wrong-patient defect from two angles, *not* "4 identity". The
verbatim evidence string. `dropped: 0`, `credits_spent: 0`. `← SWIPE`

---

## SLIDE 4 — Demo 2: the same test five times  ·  ends ~10:22

**Say (deck):** 5 records, 15 problems I planted, 5 runs, temp 0, only the order changed. The
four scoring words (caught / misgraded / silent miss / false alarm), with the 112% oxygen
example. Raise the fair objection yourself: the key is my rules' own output, so 15/15 is by
construction — the result that matters is the AI answering differently five times. `SWIPE →`

**Type:**
```
./demo2.sh
```
Runs two steps with an Enter-pause between:
1. `compare --runs 5 --mode replay` → caught 14, 14, 15, 14, 12 · false alarms 0, 0, 7, 4, 0
2. the same scorecard as a SQL table over the saved results

**Point at:** step 2 is SQL over the saved results, not my summary. (Per-problem detail is cut
for time — don't narrate it.) `← SWIPE`

---

## SLIDE 5 — Demo 3: the whole month  ·  ends ~12:49

**Say (deck):** reads all 40 June records at once; 4 patterns planted and committed in advance;
SQL goes first; the framing rule (bias in the writing, synthetic data, doesn't accuse anyone).
`SWIPE →`

**Type:**
```
./demo3.sh
```
Runs four steps with an Enter-pause between each:
1. loads the month's 40 records on camera (`generate_month` + load) — talk over it
2. `audit --month 2026-06 --mode replay --grade` → 4 patterns, 0 dropped, 0 credits, 4 caught
3. the zip asymmetry as SQL → Black 8/10 = 80%, every other group 0% (blank-race row = the 7
   batch fixtures; call it out)
4. the grade table → 4 of 4 `caught`

**Point at:** 4 of 4 caught, 0 dropped, 0 credits. **Do not narrate the grader caveat** —
it's in the if-asked list for Mahima's Q&A, not the take. `← SWIPE`

---

## SLIDE 6 — Key Outcomes  ·  ends ~13:13

**Say:** every number came from SQL or a recording. Both halves held — agents won the reading
jobs, rules won the fixed-spec jobs identically every time. **57 words — don't pad it.**

**Type:** nothing. Deck only. (No swiping from here to the end.)

---

## SLIDE 7 — The guard caught the AI twice  ·  ends ~14:08

**Say:** both live runs came back malformed, the guard quarantined both, nothing bad saved. A
tested repair against the real broken response (still in the repo as evidence), 2 credits, no
third try. One line: I did not let a language model decide what runs next over patient data.

**Type:** nothing. Deck only.

---

## SLIDE 8 — Way Forward  ·  ends ~15:13

**Say:** four things — a referee agent for specialist disagreements, a web page, the database
on a real server, and the honest caveat that real notes are messier than synthetic ones.

**Type:** nothing. Deck only.

---

## SLIDE 9 — Close  ·  ends ~15:44

**Say:** every claim traces to a recording or a query you can run; rules kept the fixed-spec
jobs, agents took the reading jobs, a non-AI layer checked their work. Each job to the tool
that's good at it. Repo's on screen. Thanks.

**Type:** nothing. Deck only. Stop the recording.

---

The full runbook (`runbook.md`) has the verified expected output for every command above, plus
the reasoning behind the load order. Use it for the dry run; use this sheet for the take.

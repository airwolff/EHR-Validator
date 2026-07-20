# Presentation script — 15-minute recorded video (plain-language rewrite)

Spoken words only. Slide numbers match `deck.html`.

**Format: ONE CONTINUOUS TAKE.** Deck on one macOS desktop, terminal on another, three-finger
swipe between them. No editing. Consequence: the whole runbook sequence has to be staged
correctly *before* recording starts — including "do not load the June month before Demo 1 runs".

**Length:** 2,202 spoken words. 15:44 at 140 wpm, 16:56 at 130 wpm. Requirement is 15 minutes,
so deliver at a normal-brisk pace and don't linger on the terminal.

**Requirement covered** (Mahima, 2026-07-01 email — the only spec): Project Objective ·
Live Project Demo · Key Outcomes · Way Forward. 15 minutes per participant. No screenshot or
format requirement of any kind.

**Rule for edits:** every number here is measured against the DB or a committed recording.
Change wording freely; do not change a number without re-running the query behind it.

---

## [SLIDE 1: Project Objective]

This project started with one number: 71.2.

Early on I sent a patient record through an AI validator, and I'd set it up properly —
temperature zero, which means I told the model to stop being creative and give me its most
predictable answer, plus a long strict prompt spelling out exactly what to check and what
format to answer in. This was not a lazy setup. The record said the patient's body temperature
was 71.2 degrees Fahrenheit. Normal is 98.6. At 71 you are dead. The AI told me the record
looked fine.

Then I wrote one line of ordinary Python — if the temperature is under 90, flag it — and it
caught the same record instantly.

That miss set the question for the whole project: which jobs should you hand to an AI, and
which jobs should you hand to a plain old script?

Here's the setup. Hospitals send each other patient records as data files, thousands a day, and
if those files are wrong then everything downstream is wrong — the bill, the reports, sometimes
the care. My project is a checkpoint at the front door. A record comes in, something inspects
it, and out comes a list: which field is broken, what's wrong with it, how bad it is, how to fix
it. That list goes into a database, and I run SQL across all of them to find trends.

One word I have to define, because I use it in a specific way: severity. Severity here means, is
this number believable — not, is this patient in danger. Blood oxygen above 100 percent is
critical because 100 is the maximum, it's impossible data. Not because anyone's dying.

And this is the claim I'll back with measurements for the rest of the talk. When the rule is
simple and you already know it, plain code wins — faster, cheaper, same answer every single
time. The AI is there for the jobs code genuinely can't do: reading the doctor's notes, noticing
when two things contradict each other, spotting a pattern nobody thought to write a rule for.

## [SLIDE 2: Two ways to check a record]

One diagram, and it's the whole system.

A record comes in. Two different things can inspect it. One is my own code — a list of rules I
wrote by hand. The other is an AI agent running Claude. Both hand back their answer in exactly
the same shape, so from there, one database and one set of SQL queries covers both. That's what
makes the comparison fair: they're filling in the same form.

Now the part this course is actually about — the night shift.

Every night, a crew of AI agents reviews the day's records. Nobody starts it, there's no button,
it runs on a schedule and it's done by morning. And it's a crew, not one agent, because they
have different jobs. A sorter decides who should read each record. An identity specialist checks
whether the record is even about the right person. A clinical specialist checks whether the
medicine makes sense. Then — and this is the one I'm proudest of — a checker reads what those
two agents claimed and throws out anything they can't prove. If an agent says the note contains
a phrase, the checker confirms that phrase is in the note, word for word. If it isn't, the
finding gets dropped before it's ever saved.

A human wrote that order of operations. Not a model.

And I should say this plainly, since it's the subject of the course: I built this with Claude
Code. The AI wrote a lot of this code. What I kept was the decisions — what the rules are, what
counts as critical, what the agents are allowed to do, and what has to be checked before
anything gets saved. Every number I'm about to show you, I got by running it, not by asking a
model whether it worked.

## [SLIDE 3: Live Project Demo — 1 of 3, the nightly agent run]

That brings us to the Live Project Demo, and everything I'm about to show you is a recording
being replayed, not a live API call. My free tier is 20 credits a month, so early on I built the
system to save every AI response to a file and re-read it later. Same output, every time, on any
machine, for free.

Segment one is where the AI earns its keep.

The record you're about to see looks perfect. Every vital sign in a normal range. Every billing
code valid. Every date sensible. My rules run over it and come back with zero problems — and my
rules are right, there is nothing wrong with any individual field.

The record is still wrong. The doctor's written note describes a 62-year-old gentleman with high
blood pressure. The structured data on that same record says 34-year-old woman.

Somebody pasted one patient's note onto another patient's chart. That happens in real hospitals,
and it's dangerous, because the next person to open this chart reads about the wrong human
being. No field-level rule can catch it — every field is individually fine. You have to read the
note and compare it against the chart.

> **[SWIPE TO TERMINAL — local validator on E-WOW-01 (0 issues), then
> `python -m app.agents --date 2026-07-14 --mode replay`. Narrate over it.]**

First the rules: clean, zero issues. Now the night shift on the same record.

Four findings come back, all critical. Look at the domain column — two say identity, two say
clinical. That is not four separate problems. It's one problem, the wrong-patient note, caught
from two directions independently: the identity agent matched the note against who the patient
is, the clinical agent matched it against the medical picture. Neither knew what the other was
doing.

Every finding carries the exact words it's based on — the sex finding quotes "62-year-old
gentleman with a history of hypertension," and the checker confirmed that phrase sits in the
note letter for letter before anything got saved. The dropped list is empty, the clean control
record came back clean, and credits spent is zero.

That's half my argument: the AI catches what rules can't reach, and what it produces is a to-do
list for a human. It never edits the chart itself.

## [SLIDE 4: Live Demo 2 of 3 — the rules win theirs]

Segment two is the other half, and this one goes against the AI.

Here's the test. Five patient records. I broke them on purpose — fifteen specific problems that I
planted myself, so I know the right answer before I start. I ran both engines over those same
five records, five separate times. Temperature stayed at zero throughout. The only thing I
changed between runs was the order the records were listed in. Not the records. Not the wording.
Just the order.

Before the numbers, the four words I score every run with. Take one of the planted problems: a
record where blood oxygen reads 112 percent. That's impossible — 100 percent is the ceiling,
it's how the measurement is defined.

If a run reports it, that's caught. That's the win.

If a run reports it but calls it a minor note instead of critical, that's misgraded. It saw the
problem and undersold it.

If a run never mentions it at all, that's a silent miss. That's the dangerous one — the report
comes back looking clean, and nobody downstream ever finds out there was anything to find.

And if a run flags a field that's perfectly fine, that's a false alarm. Nothing's broken, but a
human still burns an afternoon proving that.

My rules took the same five runs and returned the identical fifteen out of fifteen every time,
in milliseconds, for free.

And I'll raise the fair objection myself: the answer key is my rules' own output. So of course
the rules score fifteen out of fifteen, they're defining the answer. That's not the result I'm
asking you to care about. The result is that the AI, graded against that same fixed key, gave me
a different answer five times out of five.

> **[SWIPE TO TERMINAL — `python -m app.agents.compare --runs 5 --mode replay`, then the Q9
> scorecard in sqlite3. Narrate over it.]**

Watch the caught column move: 14, 14, 15, 14, 12. Now the false alarms: zero, zero, seven, four,
zero. Same records. Same settings. Different answers. And this table is SQL over the saved
results — the database talking, not me summarizing.

Here's the sentence this segment exists to earn. Same five records, five runs each. The rules:
fifteen out of fifteen, identical, every time. The AI: a different answer every time I shuffled
the order — one silent miss, five wrong severity levels, eleven invented problems, one of them
on a record I had certified as clean.

The thing it missed this time was a broken timestamp. Back at the start, the thing it missed was
the 71.2-degree temperature. The misses move around. That's the point — you can't patch your way
to reliable when the answer changes based on what order you handed it the paperwork.

## [SLIDE 5: Live Demo 3 of 3 — the month-end auditor]

Segment three. In my original pitch this was the someday feature, and it's built.

The night-shift agents read one record at a time. This one reads the whole month at once — 40
June records from three different hospital systems. I planted four problems in that month before
I started, wrote the answers down, and committed them so I couldn't move the goalposts
afterward.

Before the AI touches anything, SQL gets first crack, and SQL already won a couple. It caught all
six records from one hospital system sending temperatures in Celsius into a field that's supposed
to be Fahrenheit. And it counted something uncomfortable: missing zip codes. Black patients, 8 of
10 records missing a zip. Every other group, zero percent.

A database can count that. What it can't do is tell you what it means or what to do about it.
That's the AI's job here, and that's the split I keep drawing all talk.

One framing rule, stated the way I wrote it in my decision log: this flags bias in how the data
was written down. It's synthetic data with an answer key I planted. It does not diagnose people,
and it does not accuse clinicians.

> **[SWIPE TO TERMINAL — `python -m app.agents.audit --month 2026-06 --mode replay --grade`,
> then Q12 and Q13 in sqlite3. Narrate over it.]**

Four patterns come back.

One: it names the Celsius problem as a root cause — not the temperatures look weird, but which
hospital system, what date it started mid-month, and the fix.

Two: it finds one paragraph copy-pasted across five unrelated patients, reworded slightly each
time, so searching for matching text finds nothing. Recognizing this is the same paragraph
wearing a different hat is exactly the job a rule can't do.

Three: the tone pattern. Two patients, same complaint, same vital signs. The woman's note says
she's anxious and insists. The man's note orders tests. No amount of SQL will ever see that.

And four, the zip codes — SQL counted it, the agent explained it and recommended an action.

Graded against my planted answers: four of four found, zero findings thrown out for bad evidence,
zero credits, because it's a replay.

## [SLIDE 6: Key Outcomes]

Key Outcomes. Every number you've seen came out of SQL over saved results or a committed
recording. None of it from memory.

Both halves held. The agents won every job that needed reading — the wrong-patient note, the
reworded copy-paste, the tone. The rules won every job with a fixed spec, and won it identically,
every time.

## [SLIDE 7: The guard, and a failure I'm keeping]

One more outcome, and it's the best evidence I have, so I'm telling it as a win even though it's
a failure.

Both times I ran the month-end auditor for real, the AI broke its own output format, the same way
both times. My guard caught both, quarantined both, and saved nothing. That is exactly what I
built it to do.

Rather than spend a third credit hoping, I had Claude write a small repair for that specific
break, and I pinned it with tests against the actual broken response — which is still in the
repo, unedited, because it's evidence. Total cost: two credits.

Which is the whole architecture in one sentence: I did not let a language model decide what runs
next over patient data.

## [SLIDE 8: Way Forward]

Way Forward — four things I'd build next.

The first one is a referee. Right now, when the identity agent and the clinical agent disagree
about the same record, nothing resolves it; both findings just sit there and a human sorts it
out. A third agent whose only job is judging that disagreement is a real job for an AI, rules
genuinely can't do it. I deferred it, I didn't drop it.

The second is a web page, so this is something a person clicks instead of something I type.

Third, moving the database onto a real server. The code is already written to run there without
changes.

And the fourth is the honest one: every record in this project is synthetic, and every problem in
it was planted by me. Real clinical notes are far messier. Before this touches anything real, the
grading and the bias framing both need to be rebuilt.

## [SLIDE 9: Close]

Every claim in this talk traces back to a saved recording or a SQL query you can run yourself.
The rules kept the jobs with fixed specs, the agents took the jobs that need reading, and a layer
that isn't AI at all checked the agents' work before any of it counted.

I gave each job to the tool that's good at it. Repo's on the screen. Thanks for watching.

---

## If-asked answers (cut from the spoken script to fit the time)

- **The grader's `invented: 1` footnote.** The month-end grade is 4/4 caught, but the grader also
  counted one "invented" pattern. Two of the planted patterns graded against the same returned
  pattern on a term tie — "identical" and "template" appear in both the copy-paste plant and the
  gender-bias plant. The grader is a deliberately dumb term-counter anyone can re-run, and I'd
  rather report what it says than tune it to look better. (`docs/decisions.md`, 2026-07-19.)
- **The grounding checker's two limits.** It is not an injection defence — an instruction hiding
  inside a note gets quoted verbatim, so the checker keeps it. And verbatim doesn't mean faithful:
  a model can quote "dysuria" out of "denies dysuria." Both are pinned by tests so they're never
  mistaken for bugs. That's why the output is a worklist a human adjudicates, not an
  auto-correction.
- **Per-problem detail from Demo 2.** A missing facility NPI — critical, blocks billing — was
  downgraded in 2 of 5 runs; a bad extract timestamp was missed outright in 1 of 5. Every row in
  that table is a rule the Python validator catches 5 of 5 times.
- **Stack.** FastAPI + Uvicorn, SQLAlchemy Core (same code runs SQLite locally, Postgres on
  Render), Lyzr agent running Claude Sonnet at temperature 0, Python 3.12.

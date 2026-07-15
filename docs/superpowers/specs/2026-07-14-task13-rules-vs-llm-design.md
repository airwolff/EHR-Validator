# Task 13 Design — Rules-vs-LLM Comparison

**Status:** approved 2026-07-14 (design review with Andy; the three big choices — shuffled runs,
prompt kept in git, results stored in the database — were settled by Q&A).

## The idea in one paragraph

**This task is one half of a two-sided argument — not "AI loses."** The other half is already
built and live-proven: the AI agents catch a wrong-patient note that passes every Python rule
(Tasks 9–12, the wow record, 2026-07-14). This half shows the reverse: for checking data against
fixed rules, plain Python code
beats an AI. Task 13 turns that argument into a number. We already have 5 test records where the
Python rules find exactly 15 problems (wrong codes, impossible vitals, missing fields, and one
record with nothing wrong). We hand those same 5 records to the AI five times and count what it
misses. The result is a sentence for the presentation like: "the AI missed the impossible
oxygen reading in 3 of 5 tries — the Python rules caught it every time, for free."

## What we're spending

Each try costs about 1 Lyzr credit (we pack all 5 records into one message). Five tries ≈ 5
credits. We have ~14.8 left this month, so ~9.8 stay in reserve in case the instructions need one
fix and a re-run. (The checklist's older "~2 credits per run" estimate was for the nightly batch,
which sends two messages; this experiment sends one.)

## Three facts that shaped the design

**1. The answer key already exists.** Run the Python rules over the 5 records and you get the
official list of problems — 15 of them as of today (checked by actually running it on
2026-07-14). The AI gets graded against that list. One small correction while checking: the
checklist says the bad oxygen value is 105; the file actually says 112.

**2. Calling the AI one record at a time is too expensive.** The existing one-record-at-a-time
path costs 1 credit per record — 5 records × 5 tries = 25 credits, more than we have. Packing
all 5 records into a single message costs ~1 credit for the whole try. So we pack.

**3. Asking the exact same question twice gets the exact same answer.** Our AI runs with
randomness turned off ("temperature 0"). Send the identical message 5 times and you'll likely
get 5 photocopies of one answer — "missed it 5 of 5 times" would secretly be one data point. So
each try must differ somehow, without changing the data itself.

## Section 1 — What one "try" (run) is

One try = one message to our existing "shell" agent on Lyzr, containing our validator
instructions plus the 5 records. The only thing that changes between tries is the **order** of
the 5 records — try 1 might send them A-B-C-D-E, try 2 sends B-E-A-C-D, and so on. The
orderings are written into the code as a fixed table (not randomly shuffled at runtime), because
the replay system files each answer under a fingerprint of the exact message — a message that
changes on its own would orphan every saved answer.

The 5 records are exactly: `payload_bad_codes`, `payload_bad_dates`, `payload_bad_values`,
`payload_clean`, `payload_missing_fields`. (The two demo records with clinical notes live in the
same folder but are NOT part of this — those belong to the note-reading story, Tasks 10–12.)

- Pro: the data never changes, so a miss in any try is a real miss, and every try gets saved and
  can be replayed offline free, forever.
- Con: we're only testing whether the order of records shakes the answer loose — a model that
  truly doesn't care about order could give the same answer all 5 times anyway. We say that out
  loud in the presentation rather than hide it.

## Section 2 — What we ask the AI

A new block of instructions, written in this repo next to the existing agent instructions and
sent inside every message. (This follows the decision already on the books: instructions live in
git, where they can be diffed and shown off, and they survive Lyzr disappearing. Andy wants this
pattern highlighted in the presentation.)

The instructions say, in plain terms:

- "You are a data-quality validator. For each record, report every defect you find."
- The same severity ladder the Python rules use — critical / warning / info rates how believable
  the *data entry* is, not how sick the patient is. The legal severity words are generated from
  the code's own constants, so the instructions can never drift out of sync with the code that
  grades the answers.
- Reply as JSON (a strict machine-readable format) with one finding per problem: which record,
  which field, what's wrong, how severe, how to fix. Each record is labeled with its filename
  (like `payload_bad_values`) so findings can be matched back.
- The "escape your quotes" rule learned from live run 1, when one unescaped quotation mark
  ruined an entire reply.

One deliberate difference from the nightly batch: **no "quote the note" requirement.** These 5
records have no clinical notes — that rule has nothing to check here.

Reading the reply reuses the existing parser, which already tolerates the ways models wrap
answers (code fences, "Here you go:" chatter) and refuses the ways they fail (apologies, cut-off
text).

- Pro: reuses the already-proven message/sending/parsing machinery end to end.
- Con: it's a second instruction-and-reply format to maintain next to the nightly batch's one.

## Section 3 — How grading works (code decides, not opinion)

The answer key is produced fresh each time by running the Python rules — so if the rules ever
change, the key updates itself instead of silently going stale.

An AI finding counts as a match when it names the same record and the same field as a rule
finding. Field names are cleaned up before comparing, so cosmetic spelling differences (like
`diagnoses[0].code` vs `diagnoses.0.code`) don't cause fake mismatches.

Every problem on the answer key gets exactly one grade per try:

- **caught** — the AI found it and rated it the same severity.
- **severity_mismatch** — the AI found it but rated it wrong (found, misgraded).
- **missed** — the AI said nothing about that field. **This is the thesis number.**

And anything the AI reports that is NOT on the answer key is a **false_alarm** — including
anything at all on the clean record, which the rules certify has zero problems.

**A garbage reply is a data point, not a crash.** If a reply can't be read as JSON, that try is
marked "unusable," the saved reply is set aside as evidence (the existing quarantine mechanism),
the remaining tries still run, and the presentation reports it honestly: "bought 5 tries, 1 came
back unreadable." We already have one real example of this from the live batch. The credit is
still spent and still counted.

- Pro: every number on the slide can be re-derived by anyone who runs the grading code.
- Con: if the AI ever finds something real that the rules don't check for, it gets graded as a
  false alarm anyway — worth one honest sentence in the presentation.

## Section 4 — Where the results live

Two new database tables, written through the same storage code as everything else:

- `comparison_runs` — one row per try: which try, when, live or replay, which record order was
  used, and whether the reply was usable.
- `comparison_results` — one row per grade: which try, which record, which field, what severity
  the rules said, what severity the AI said, and the grade (caught / severity_mismatch / missed /
  false_alarm). When the AI missed, its severity column is empty; when it false-alarmed, the
  rules' severity column is empty.

The headline numbers come from new UPPERCASE queries added to `db/queries.sql` — this is an SQL
portfolio, so the strongest version of the slide is "the thesis number is a SQL query over my own
experiment data":

- For each known problem: missed in how many of the N tries?
- Per try: how many caught / missed / misgraded / false alarms?
- Where the AI found a problem but graded it differently: what did it say vs the rules?
- How many tries came back unusable?

Housekeeping note: brand-new *tables* appear automatically on startup; only new *columns* on
existing tables need the full database-reset dance. This design adds tables only, so no reset.

## Section 5 — How you run it

```
python -m app.agents.compare --runs 5 --mode replay
python -m app.agents.compare --runs 5 --mode live
```

- Works like the existing batch command: reads `.env` itself, prints a one-line refusal if
  something's wrong instead of a stack trace.
- **Live** mode spends real credits, and every call goes through the existing credit ledger
  (charged before the network call, same as always — do not reorder). Every reply is saved.
- **Replay** mode re-grades from the saved replies at zero cost.
- Tries are independent: one unreadable reply doesn't stop the rest.

The demo story: pay once to run it live, then replay it on stage for free, every time.

## Section 6 — Tests come first (per the loop)

All tests run offline against authored saved-replies made with the existing `record_reply`
helper (never hand-written reply files — those can't be replayed). Pinned before the real code
is trusted:

- **Grading:** one authored try containing a planted miss, a false alarm, and a severity
  mismatch grades exactly as expected; one fully-correct try grades all-caught.
- **Message stability:** the same try number always produces the byte-identical message;
  different try numbers produce different orderings (and therefore different fingerprints).
- **Garbage replies:** an unreadable reply is counted and quarantined, later tries still run,
  and the try's row says unusable.
- **Storage:** both tables get written through the same path the command uses.
- **Drift guard:** a separate test pins "the answer key has 15 problems today," so if a fixture
  or rule quietly changes, a test goes red instead of the experiment silently grading against a
  different key.

## Not in this task

- The two clinical-note demo records and anything about the nightly batch, the specialists, or
  the evidence guard.
- Buying the paid Lyzr plan — only if 5 tries prove too few or the instructions need heavy
  iteration (open question #6).

## For the presentation (docs/for-review.md, after the runs)

- The number itself: "missed X of 15 known problems, in Y of 5 tries."
- The prompts-in-git shell-agent pattern (diffable, survives Lyzr) — call it out explicitly.
- The two honest caveats, spoken aloud: (1) with randomness off, we vary record order to get
  independent tries — it probes order-sensitivity, not true randomness; (2) a novel-but-correct
  AI finding would be graded as a false alarm here.

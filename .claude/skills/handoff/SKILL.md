---
name: handoff
description: Use at the end of a session, when context is getting tight, when a milestone lands, or when the user asks for a handoff — rewrites docs/handoff.md so a fresh session can pick the work up cold, and runs the end-of-session ritual from docs/session-protocol.md.
---

# Session Handoff — EHR Triage Pipeline

Rewrite `docs/handoff.md` so another session, with **zero** conversation history, can continue
without re-asking anything already settled.

Sessions here span days. A stale handoff is worse than none: it reads as authoritative and sends
the next session down a dead end. The 2026-07-11 handoff listed "commit the protocol docs" as the
next step when that commit had already landed — it cost the next session real time to notice.

## Step 1 — Go look. Do not reconstruct from memory.

Run these and use the *output*, not your recollection:

```bash
git rev-parse --short HEAD          # the HEAD to record in the staleness block
git log --oneline -5                # what actually landed
git status -s                       # what's actually uncommitted
python -m pytest -q                 # is the suite green RIGHT NOW?
python -c "import app.main; print('boots')"
```

Then read what you're about to point at: `docs/phase-checklist.md` (what's ticked),
`docs/open-questions.md` (what's still blocking). Verify every path, sha, filename, and command
you cite. A wrong sha makes the whole document untrustworthy.

## Step 2 — Pick a depth

- **Deep session** (multiple decisions, code landed, a gnarly thread resolved) → full structure below.
- **Thin session** (one topic, exploration, nothing committed) → keep only *Staleness block*,
  *Where we are*, *Next step*. Don't pad it.

When unsure, lean comprehensive.

## Step 3 — Write it

Overwrite `docs/handoff.md` entirely — it is throwaway current state, and **git history is the
chain**. Do not append, do not keep an archive section, do not create `handoff-2.md`.

```markdown
# Handoff — EHR Triage Pipeline — <YYYY-MM-DD>

## Staleness block (check before trusting)
- **Written:** <date>
- **HEAD at write time:** `<short sha>` (branch `<branch>`)
- **Uncommitted at write time:** <exact `git status -s` lines, or "clean">
- **Tests:** <e.g. "12 passed" — the actual number you just saw, or "RED: <what fails>">
- **Boots?** <yes/no — from the actual command>
- **Staleness test:** if `git rev-parse --short HEAD` ≠ `<sha>` or `git status -s` differs, this
  handoff is stale — trust git + code, rewrite it early.

## Where we are
What is *actually in place*. Commands run, values observed, evidence seen.

## ► Next step (do this first)
The specific next action — the actual file or command, not "continue the work."

## Dead ends — don't retry
What was tried and failed, and why. Omitting this sends the next session down the same hole.

## Gotchas / carry-forward
What the next session would otherwise rediscover the hard way.
```

## Step 4 — The rest of the end-of-session ritual

The handoff is one of four steps in `docs/session-protocol.md`. Do the others:

- **Log any real decision** in `docs/decisions.md` — append only (a hook enforces this; a reversal
  is a *new* entry that supersedes the old one by name, never an edit to the old one).
- **Tick `docs/phase-checklist.md`** — only for things you verified *by running*.
- **Move answered items** in `docs/open-questions.md`.

## Rules

- **Specific over complete.** Names, paths, shas, the exact next command. Never "continue the work."
- **Verified ≠ built.** On this project "verified" means you ran it and read the output. If you
  wrote code but never executed it, the handoff says *"written, not run"* — do not write "done."
- **Point, don't copy.** Reference the spec, the plan, and `decisions.md` by path. Duplicated
  content goes stale and then lies. The handoff records *state*; the other docs hold the *why*.
- **Never paste a secret.** No Lyzr key, no `.env` contents — not even redacted-looking fragments.
- **Quality gate — do not finalize a handoff that has:** `TODO`/placeholder text, an empty required
  section, a secret, or a "done" claim you did not verify by running.
- **Commit it.** Unlike the sibling repos' handoff skills, this project *does* commit the handoff —
  overwrite-plus-git-history is how handoff history exists here. Commit style `[docs] ...`, and get
  **explicit approval first**, like any other commit.

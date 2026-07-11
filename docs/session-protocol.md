# Session Protocol — how we hand off between sessions

The ritual that keeps work from getting lost between sessions. Distilled from external best practice
(ADRs; Claude Code / agent session-handoff guidance) and this project's own rules. Keep it short and
actually follow it.

---

## The doc map — one home per kind of writing (never duplicate)

| Doc | Answers | Lifecycle |
|---|---|---|
| `CLAUDE.md` | "What is this project + the rules?" (the stable map) | Edit in place; keep tight |
| `docs/handoff.md` | "Where am I right now?" (throwaway current state) | **Overwrite each session** (git history is the chain) |
| `docs/decisions.md` | "Why did we choose this?" (durable, ADR-lite) | **Append-only** |
| `docs/open-questions.md` | "What's undecided / blocked?" | Update status as answers land |
| `docs/phase-checklist.md` | "What do I do next?" (current phase scope) | Rewrite per phase; tick only when verified |
| `docs/for-review.md` | "What to raise at a mentor checkpoint + arguments to protect" | New up top; resolved → bottom |
| `docs/specs/`, `docs/superpowers/plans/` | Approved design + implementation plan | Reference by path; don't restate |
| Memory (`~/.claude/.../memory/`) | **Who you are + how you work** (cross-project, auto-loaded) | One fact per file + index line |

**The memory boundary (you asked about this):** memory is for *you and your preferences* across every
project (auto-loaded). `decisions.md` is the *project's* durable why (in-repo). `handoff.md` is
throwaway state. If a fact is project-specific and durable → `decisions.md`, not memory. No separate
project "memory doc" — it would duplicate these.

---

## Start-of-session ritual

1. Read `CLAUDE.md`, then `docs/phase-checklist.md`, then `docs/handoff.md`.
2. **Verify the handoff before trusting it — it's a claim, not proof.** Run the staleness check:

   ```bash
   git rev-parse --short HEAD          # does it match the handoff's "HEAD"?
   git log --oneline -5                 # any commits since the handoff was written?
   git status -s                        # do the uncommitted files match?
   python -c "import app.main; print('boots')"   # does it still boot?
   ```
   If HEAD moved, commits appeared, or files changed since the handoff timestamp → the handoff is
   **stale**; trust git + the code over the prose, and rewrite the handoff early.

---

## End-of-session ritual

1. **Rewrite `docs/handoff.md`** from the template (see the file). Fill the staleness block from the
   commands above. Record what's *actually in place* — commands run, values set, evidence observed —
   not just "done."
2. **Log any real decision** in `docs/decisions.md` (see the "log a decision when…" trigger there).
3. **Move answered items** in `open-questions.md`; **tick `phase-checklist.md`** only for things you
   verified by running.
4. **Quality gate** — do NOT finalize a handoff that has: `TODO`/placeholder text, empty required
   sections, a secret pasted in, or a "done" box you didn't verify by running.

---

## When to write a handoff (triggers)

- The session is ending.
- A milestone landed (a task/feature is green).
- ~5+ files changed or a gnarly debugging thread just resolved.
- Context is filling up (compact/clear is coming).
- You're about to switch tasks.

## Anti-patterns (from the research)

- Vague status ("made progress") instead of specifics (commands, values, file:line).
- Omitting **failed attempts** — that sends the next session down the same dead end.
- Recording *what* without *why* — decisions need rationale.
- Duplicating the spec/plan into the handoff — reference by path instead; copies rot.

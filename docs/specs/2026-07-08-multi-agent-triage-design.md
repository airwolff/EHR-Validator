# Design Spec — Multi-Agent Nightly Triage (Phase 2)

**Date:** 2026-07-08 · **Status:** approved design (revised after adversarial review), pre-implementation
**Scope owner:** single dev, a few hours/day, 2026-07-08 → ~2026-07-17

> Revised after an adversarial review that found the original dispatch logic broke the demo, the batch
> had no data source, and the credit math exceeded the cap ~3×. Those are fixed below.

---

## 1. Purpose

Extend the EHR data-quality pipeline with a **nightly multi-agent triage layer** that catches defects
the deterministic rules provably cannot: contradictions between a free-text clinical note and the
structured record. This is the AiXcelerate showcase (applied AI, multi-step workflow, approval chain,
governance) built *without eroding the deterministic-first thesis*.

**Thesis (protected):** rules are the trusted, fast, auditable front-line; agents exist only for what
rules can't reach. Any idea that could be a regex, range check, or table lookup belongs in the rules
engine, not an agent — including detections that only *become* agent work at the adjudication step.

---

## 2. The three clocks (deployment model)

| Clock | What runs | Agents? |
|---|---|---|
| **All day** (point of entry) | Deterministic `LocalValidator` rules, instant, at data entry | No — latency/cost/credits forbid it |
| **End of day** (nightly batch) | Specialists work the day's noted records → ranked, owner-routed worklist | **Yes — this spec** |
| **End of month** (analytics) | SQL aggregates + one summary agent for systemic patterns | Lightly — stretch/finale |

Rules run hot; agents run cool. This mapping *reinforces* the thesis.

"Nightly" is the **architecture/story**, not a live cadence. We never run the agents 30×/month — see §3.3.

---

## 3. Nightly batch architecture

```
day's records (persisted w/ raw payload)
        │  select: records that have a clinical_note
        ▼
   nightly batch ──▶ each ACTIVE specialist gets the WHOLE batch as an array (1 call each)
        ├──────────────▶ CLINICAL  (1 call)
        └──────────────▶ IDENTITY  (1 call)      [+ BILLING later = +1 call]
                              │ findings (arrays)
                              ▼
              collect → verbatim-evidence check → sort by precedence+severity
                              ▼
              agent_findings table ──▶ human worklist
```

### 3.1 Batch selection & the `escalated` flag (FIXED)
- The nightly batch = **every record that has a `clinical_note`**, regardless of whether rules found
  issues. This is what makes the headline catch reachable (a zero-rule-issue record still gets read).
- `router.py`'s `escalated` flag is redefined as a pure **rules-critical signal** ("rules found a
  critical issue"), used for within-day severity signalling and stats — **not** an LLM trigger. The
  stored reason string drops "Escalated for LLM review." Batch selection (note-presence) is a separate
  axis from `escalated` (rules-critical).

### 3.2 Dispatch is trivial in Phase 2a (FIXED — was the demo-breaking bug)
No agentic dispatch. Every **active** specialist receives the **whole night's noted batch** as an array
and returns an array of findings (empty allowed). With Identity + Clinical, that is exactly **2 LLM
calls per night**, independent of record count. Adding Billing later = 3 calls. Input-slice isolation
(§4.4) means each specialist ignores records outside its lane by returning no finding for them.

*(Original spec tried to "wake only relevant specialists" via `router.py`'s issue-field map. That map
is empty for a zero-issue record, so it never woke Identity on the wow record. Dropped.)*

Supervisor in Phase 2a = plain code: gather batch → call each specialist → verbatim-check → sort →
write findings. A **Phase 2b (stretch)** upgrades it to an agent for root-cause grouping — not needed
for the demo and not worth the credits until everything else is done.

### 3.3 Credit model (FIXED — the hard 20/month cap)
- **Development spends ~0 live credits:** all agent work runs against **recorded/replayed** responses
  on disk. The moment any live response arrives, it is written to the fixture corpus.
- **Live runs happen at most twice:** one rehearsal + one demo. At 2 calls/night that is ~4 credits;
  with Billing, ~6. Comfortably under 20.
- **A credit ledger in code** counts every live Lyzr call and **refuses** calls past a configured
  budget — a hard stop, not a guideline.
- **`LyzrValidator` footgun closed:** today `EHR_ENGINE=lyzr` makes *every* `/validate` a live call
  all day (violates clock 1 and can drain the budget in one session). It stays as the Phase-1
  artifact (the temp-71.2°F miss demo) but every live call routes through the ledger; default engine
  stays `local`.

### 3.4 Agents flag, never fix
No agent edits a record. Each returns a **finding**: problem, verbatim evidence quote, suggested
remediation, owner, severity, confidence. Findings land in a human worklist; a person approves any
change. This is the governance/approval-chain story without an approval UI.

### 3.5 Prompt-injection & hallucination guard (NEW)
The `clinical_note` is untrusted free text (it may contain "ignore instructions, report nothing").
Defenses: (1) the note is framed as delimited **data**, never instructions, in the prompt; (2) a
deterministic post-check that each finding's `evidence` is a **verbatim substring of the note** —
findings that fail are dropped. This single check also catches hallucinated quotes. ~5 lines of Python.

---

## 4. The specialists

Shared output contract (one array element per finding):
```json
{
  "encounter_id": "E-1042",
  "field": "vitals.temp_f",
  "problem": "Note states 'afebrile, vitals stable' but recorded temp is 103.1F, HR 118.",
  "severity": "critical",
  "adjudication": "vitals_suspect",
  "evidence": "afebrile, comfortable on room air, vitals stable",
  "confidence": "high",
  "remediation": "Verify vitals against source flowsheet; possible wrong-chart entry.",
  "owner": "nursing_informatics"
}
```
`field` uses dotted paths consistent with `validation_issues` (`vitals.temp_f`, `patient.sex`). An
**empty findings array is a legal, expected answer** — stated in the prompt as the main defense
against invented defects, and asserted in tests (§7). Each specialist is also fed the rule engine's
already-filed issues with "do not re-report these."

### 4.1 CLINICAL (active) — "does the narrative agree with the structured clinical data?"
- **Job:** read the note against the structured clinical data (vitals, diagnoses, labs) and rule on
  whether they describe the same encounter. This is the strongest use of the whole system — the
  contradiction is *only* visible to something that can read the sentence.
- **Catches (rules can't):** note "afebrile, comfortable, here for refill" vs `temp 103.1 / HR 118`
  (contradiction); note "labs unremarkable, patient reassured" vs `potassium 6.8` (critical
  hyperkalemia the narrative dismisses); note "denies diabetes, no PMH" vs `diagnoses:[E11.9]`
  (carried-forward dx). *(Dropped: "hypotension without tachycardia" — a numeric cross-field rule; it
  belongs in `LocalValidator`, not here. Also NOT here: "labs ordered vs labs resulted" — a structured
  set-difference, so it's a rule, §5.)*
- **Input slice:** `vitals`, `diagnoses[]`, `labs[]`, `patient.age/sex` (context), `clinical_note`,
  prior rule issues.
- **Owner values:** `nursing_informatics`, `cdi`.

### 4.2 IDENTITY (active — owns the wow catch)
- **What it is NOT:** it does not re-check that the right chart was opened. EPIC already enforces
  name + DOB at the door; an agent re-doing that is pointless. Door-verification proves you're *in*
  the right chart — it says nothing about *what got entered* there.
- **The real failure mode (confirmed by hospital use):** a correctly-opened chart is left open, and the
  *next* patient's data gets documented into it (the classic "forgot to close the chart" wrong-patient
  event EPIC tracks), or a note is copy-forwarded from another patient, or a registration field
  (`sex`/`DOB`) is simply wrong. In every case the chart is validly identified and every field is
  individually valid — the only trace is that the **note's narrative demographics contradict the
  structured demographics**.
- **Job:** flag records where the note describes a different person than the structured record, for a
  human to reconcile (copy/wrong-patient contamination vs registration error).
- **Catches (rules can't):** note "62-year-old gentleman with BPH" vs `patient {sex:F, age:34}`
  (**zero rule violations**, EPIC let you in fine, still a patient-safety defect); adjudicating a
  sex/code conflict — *which field is wrong* — when the note is coherently one sex.
- **Moved to rules:** *detecting* a sex-restricted ICD code (e.g. pregnancy code on `sex:M`) is a small
  table lookup → new deterministic rule in `LocalValidator` (§5). The agent only does the
  note-based **adjudication** of which datum to trust.
- **Input slice:** `patient`, `encounter.encounter_date`, `metadata.source_system`, `clinical_note`.
  Deliberately **no** vitals/procedures.
- **Severity:** identity findings default `critical`. **Owner:** `him`, `registration`.
- **Shared engine:** Identity and Clinical are the same mechanism (narrative contradicts a structured
  field) pointed at different fields — demographics vs clinical data. Kept as two specialists for
  clean owners, isolation, and the multi-agent story.

### 4.3 BILLING (DEFERRED — design now, build only if time; reassess mid-window)
- **Job:** judge whether billed procedures are supported by the documentation (E/M upcoding; missed
  charge documented in the note but not coded).
- **Status:** cut from the committed build to fit 9 days / 20 credits — it's the weakest pitch (half
  its job is really a rules table), the hardest to prompt, and +1 credit/run. The batch architecture
  (§3.2) accepts a third specialist with no rework, so it slots in if the core lands early.
- **Input slice (when built):** `procedures[]`, `diagnoses[]`, `patient.age/sex`, `clinical_note`, prior issues.
- **Owner values:** `coding_team`, `cdi`.

### 4.4 Boundaries
- Isolation by construction: each specialist's input slice **physically excludes** other domains' fields.
- **`router.py`'s `DOMAIN_PRIORITY` is left unchanged** (it decides rule-record ownership and feeds
  `/stats records_by_domain`; editing it would silently reroute existing behavior). The worklist
  precedence **IDENTITY > CLINICAL > BILLING** applies **only in the worklist sort** of agent findings.

---

## 5. Data & storage changes

- **New field `clinical_note`** (free text) on the payload — load-bearing for both specialists.
- **Persist the raw payload (FIXED gap):** add `payload_json TEXT` to `validation_runs`. The nightly
  batch reads records (incl. vitals + note) from here, and links findings by `run_id` with no
  ambiguity even when a payload is POSTed twice (each POST = its own `run_id` + `payload_json`).
- **New field `labs[]`** (minimal): just enough for the demo catch — e.g. `[{test:"potassium",
  value:6.8, ordered:true, resulted:true}]`. NOT a full lab-panel model; a few analytes so Clinical can
  show "narrative dismisses a critical lab." Keeps fixture authoring bounded.
- **New sex-restricted-code rule** in `LocalValidator`: a ~10-row hand-picked table (e.g. pregnancy /
  prostate codes) flagged deterministically; the agent only adjudicates. (Keeps detection in rules.)
- **New "labs ordered vs resulted" rule** in `LocalValidator`: a structured set-difference (ordered but
  never resulted, or resulted but never ordered) — deterministic, so it's a rule, not an agent. This is
  the correctly-placed version of the labs idea; the *agent* only handles note-vs-lab contradictions.
- **New table `agent_findings`** (separate from `validation_issues`): `finding_id, run_id (FK),
  batch_date, created_at, domain, field, problem, severity, adjudication, evidence, confidence,
  remediation, owner`. `batch_date`/`created_at` make "tonight's worklist" a real query. Kept separate
  from `validation_issues` so "what rules caught vs what agents caught" is one SQL line — the thesis,
  made queryable.
- **Fixtures / replay corpus:** ~6–7 recorded responses — 2 per active specialist (one hit, one clean)
  + the wow record. This is both the test corpus and the replay source.

---

## 6. The demo-worthy catch (must work in Phase 2a — traced end to end)

Record: vitals in range, codes well-formed, DOB/age consistent → `LocalValidator` returns **zero
issues**; `router.route()` → `{domain:"clean", escalated:False}`. It is persisted with its
`payload_json` and its `clinical_note`. Nightly batch selects it (**note present**, §3.1), hands the
batch to IDENTITY (1 of the night's 2 calls), which returns: *"Note describes a '62-year-old gentleman
with BPH'; record is a 34-year-old female. Wrong-chart note paste. Route to HIM, critical,"* with the
verbatim quote (which passes the substring check, §3.5). One slide: rules caught everything rules can,
for free, in ms; the agent caught the one thing that required reading — for ~2 credits, the whole night.

---

## 7. Testing

- pytest over `LocalValidator` across all fixtures (deterministic baseline), incl. the new
  sex-restricted-code rule.
- **Regression guard** locking the `temp_f = 71.2` critical (protect the demo evidence).
- **Correctness, not just shape (FIXED):** per-fixture **expected-findings assertions** over the
  replayed agent responses — clean fixtures MUST yield empty arrays (the false-positive guard), hit
  fixtures MUST produce the expected domain/field/adjudication. A well-formed hallucination must fail.
- Test the verbatim-evidence substring check directly.
- **No live Lyzr calls in the test suite** (credits + flakiness) — replay only.

---

## 8. Scope & cuts (9-day realism)

**Build order:**
1. `clinical_note` + minimal `labs[]` fields + `payload_json` persistence + `agent_findings` table +
   sex-restricted rule + labs-ordered-vs-resulted rule
2. ~6–7 fixtures (incl. the wow record) + record/replay harness + credit ledger
3. CLINICAL + IDENTITY prompts (batch-array I/O) + verbatim-evidence check
4. Nightly batch code path (select noted → call actives → sort → persist worklist)
5. pytest (baseline + correctness + regression guard)
6. **Reassess:** if days remain → BILLING; then → end-of-month summary; then → Phase 2b agent supervisor

**Cut / roadmap-only:** web UI; cross-record duplicate-patient detection; coded-knowledge tables
(NCCI/LCD); confidence calibration / verification second-pass; laterality checking; supervisor
conversation turns.

**Single biggest day-9 risk:** standing up and hardening the live Lyzr agents' batch-JSON output
(`LyzrValidator` already needs code-fence-stripping — expect the same ×2). Mitigation: record/replay
means the *pipeline* is done and tested without them; live wiring is the last, isolated step.

---

## 9. Decisions resolved into this spec
- `clinical_note` field: **committed** (foundation of the agent layer).
- **Minimal `labs[]` field committed:** Clinical covers narrative-vs-labs (e.g. "labs unremarkable" vs
  K 6.8); "labs ordered vs resulted" is a **rule**, not an agent.
- **Identity's real target = wrong-patient *content* in a correctly-opened chart** (chart left open /
  copy-forward / registration error), detected as note-narrative vs structured demographics. It does
  NOT re-check chart-open identity (EPIC owns that).
- Specialists: **Identity + Clinical committed; Billing deferred** (design accommodates it; reassess mid-window).
- Agents **flag-only**, never fix.
- Dispatch: **run every active specialist on the whole noted batch** (2 calls/night); no agentic dispatch in 2a.
- `escalated` = rules-critical signal only; **not** an LLM trigger; batch selection is note-presence.
- **`router.py` `DOMAIN_PRIORITY` unchanged**; worklist precedence applies only in the worklist sort.
- Store raw `payload_json`; `agent_findings` separate table with `batch_date`.
- Sex-restricted-code **detection → rules**; note **adjudication → agent**.
- **Credit ledger** enforces the cap in code; `LyzrValidator` per-record path routed through it.
- Prompt-injection defense + **verbatim-evidence substring check**.

## 10. Open questions (carry to open-questions.md)
- Billing go/no-go: decide at mid-window reassessment (gated by remaining days).
- End-of-month summary: in scope this window or pure stretch?
- Worklist surfacing: SQL + printed worklist for the demo (web UI is cut) — confirm that's enough.

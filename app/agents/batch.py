"""The nightly batch — the only place the agents actually run.

Pick up every record that carries a clinical note and hasn't been reviewed → ask each
specialist once (one call per specialist, not per record) → read the replies → throw out
everything that isn't grounded in that record's own note → save what survives → mark the
records reviewed. Offline by default: mode="replay" reads recorded answers and costs nothing.

Three rules hold this together, and all three are about not lying to ourselves later:

**All or nothing.** Stamping a record 'processed' takes it out of the inbox permanently. So
if any specialist's reply cannot be read, the batch writes NOTHING and raises: the records
stay in the inbox and a retry re-asks. The alternative — stamp what we have — silently
records half a review as a whole one, and no future run will ever notice.

**A cleared record is still a reviewed record.** Zero findings is an answer. It gets stamped
like any other, or the batch re-reads (and in live mode re-pays for) every clean record on
every run, forever.

**Every drop is counted.** Two kinds: a finding whose quote is not in the note (the model
made the words up), and a finding naming a record that wasn't in the batch (the model made
the patient up). Neither reaches the worklist, and both come back in the result — the drop
rate is the presentation's evidence, and a silent drop is a lost argument.

The specialist, not the model, decides a finding's `domain` and `owner`: the clinical agent
is by construction the clinical domain. Those are stamped BEFORE the guard runs, so the model
is never marked down on a field we were going to overwrite anyway.
"""
import os
import re

from app import store
from app.agents._fileio import exclusive_lock
from app.agents.schema import partition_findings
from app.agents.specialists import (
    SPECIALISTS,
    ResponseUnparseable,
    build_message,
    parse_findings,
    record_ids,
)
from app.agents.transport import get_response, quarantine_recording

UNKNOWN_RECORD_ID = "unknown_record_id"

# The key the worklist is queried by. "2026-7-13" would file findings where nobody looks —
# and the records would still be stamped, so they would never come back. Same reason the
# ledger validates its month key.
BATCH_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class BatchAborted(RuntimeError):
    """A specialist's reply could not be read, so the batch wrote nothing.

    Deliberately fatal. The records are still in the inbox; run it again. Task 13 counts how
    often this happens — an agent that periodically returns prose is exactly the unreliability
    the deterministic validator does not have.

    `credits_spent` is how many credits the failed run cost. Once this is raised nobody can
    reconstruct it, and "the LLM cost N credits and returned unusable output in M of N runs"
    is precisely the sentence Task 13 exists to produce.
    """

    def __init__(self, message, credits_spent=0):
        super().__init__(message)
        self.credits_spent = credits_spent


def run_nightly_batch(batch_date, *, mode="replay", recordings_dir, agent_id=None,
                      ledger=None, active=("clinical", "identity")):
    """Run the agent batch over every unreviewed noted record.

    Returns {"worklist": [...], "dropped": [{"finding", "reasons", "specialist"}],
             "counts": {"records", "returned", "kept", "dropped", "unknown_record",
                        "credits_spent"}}

    The counts are not decoration: `returned` vs `kept` vs `dropped` IS the rules-vs-LLM
    argument, and nothing downstream can reconstruct them once the findings are filtered.

    Only one batch runs at a time. Two overlapping runs — a cron firing while someone runs it
    by hand — would both read the same unstamped inbox, both ask the agents, and both write:
    every finding stored twice, the worklist double-counted, and the drop rate measured over
    twice the denominator.
    """
    with exclusive_lock(os.path.join(recordings_dir, ".batch.lock")):
        return _run_batch(batch_date, mode, recordings_dir, agent_id, ledger, active)


def _run_batch(batch_date, mode, recordings_dir, agent_id, ledger, active):
    if not BATCH_DATE.match(str(batch_date)):
        raise ValueError(
            f"batch_date must be YYYY-MM-DD, got {batch_date!r}. Refusing to file findings "
            f"under a key nothing will query."
        )

    records = store.get_noted_records()
    if not records:
        # NOT an empty worklist: the day's findings still stand, they were just written by an
        # earlier run. Returning [] here would tell a demo audience the pipeline lost them.
        return _result(store.get_worklist(batch_date), [],
                       {"records": 0, "returned": 0, "kept": 0, "dropped": 0,
                        "unknown_record": 0, "credits_spent": 0})

    run_id_for = record_ids(records)                       # {record_id seen by the agent: run_id}
    notes = {r["run_id"]: (r["payload"].get("clinical_note") or "") for r in records}
    findings_by_run = {r["run_id"]: [] for r in records}   # every record gets an entry, even []
    dropped = []
    credits_spent = 0

    # Ask every specialist BEFORE writing anything. A reply we cannot read aborts the whole
    # batch, and an abort must not leave half the review persisted.
    for name in active:
        specialist = SPECIALISTS[name]
        message = build_message(specialist, records)
        spent_before = ledger.spent() if ledger is not None else 0
        raw = get_response(name, message, mode=mode, recordings_dir=recordings_dir,
                           agent_id=agent_id, ledger=ledger)
        if ledger is not None:
            credits_spent += ledger.spent() - spent_before

        try:
            findings = parse_findings(raw)
        except ResponseUnparseable as exc:
            # The reply was recorded before anyone tried to read it (transport records first,
            # deliberately). Left in place, that junk recording replays on every future offline
            # run and wedges the pipeline permanently. Move it aside — it is evidence, not
            # garbage, so it is kept as .rejected rather than deleted.
            rejected = quarantine_recording(recordings_dir, name, message)
            raise BatchAborted(
                f"The {name} specialist's reply could not be read. Nothing was written and no "
                f"record was marked processed — they are all still in the inbox, so run it "
                f"again. The bad reply was moved to quarantine ({rejected}); replay will now "
                f"say 'no recording' instead of failing on it forever. ({exc})",
                credits_spent=credits_spent,
            ) from None

        for finding in findings:
            _sort_one(finding, specialist, run_id_for, findings_by_run, dropped)

    # Now judge the findings — once per RECORD, not once per finding: partition_findings
    # normalises the note a single time per call and reuses it across the list, which is the
    # whole reason it takes one.
    kept_by_run = {}
    for run_id, found in findings_by_run.items():
        kept, dropped_here = partition_findings(found, notes[run_id])
        kept_by_run[run_id] = kept
        # `domain` was stamped from the specialist above, so it still identifies who said it.
        dropped.extend({**drop, "specialist": drop["finding"].get("domain")}
                       for drop in dropped_here)

    # One write per record, both specialists' findings together: findings and the processed
    # marker land in a single transaction (store.record_agent_result), so the record cannot be
    # stamped without its findings or counted twice.
    for run_id, kept in kept_by_run.items():
        store.record_agent_result(run_id, kept, batch_date)

    kept_count = sum(len(v) for v in kept_by_run.values())
    return _result(
        store.get_worklist(batch_date),
        dropped,
        {
            "records": len(records),
            "returned": kept_count + len(dropped),
            "kept": kept_count,
            "dropped": len(dropped),
            "unknown_record": sum(1 for d in dropped if UNKNOWN_RECORD_ID in d["reasons"]),
            "credits_spent": credits_spent,
        },
    )


def _sort_one(finding, specialist, run_id_for, findings_by_run, dropped):
    """Attach one finding to its record, or drop it if we cannot say which record it is about.

    The evidence guard runs later, once per record. This only answers "whose finding is this?"
    """
    if not isinstance(finding, dict):
        dropped.append({"finding": finding, "reasons": ["malformed"],
                        "specialist": specialist.name})
        return

    # The model invented (or garbled) the record id: there is no patient to attach this to,
    # and guessing one is how a finding lands on the wrong chart. Counted separately from a
    # fabricated quote — a different failure, and a different number.
    run_id = run_id_for.get(finding.get("record_id"))
    if run_id is None:
        dropped.append({"finding": finding, "reasons": [UNKNOWN_RECORD_ID],
                        "specialist": specialist.name})
        return

    # Stamp what WE know before the guard judges what the model said. The clinical agent is
    # the clinical domain by construction; marking the model down for fumbling a field we
    # overwrite anyway would inflate the very drop rate we report.
    finding["domain"] = specialist.name
    if not str(finding.get("owner") or "").strip():
        finding["owner"] = specialist.default_owner

    findings_by_run[run_id].append(finding)


def _result(worklist, dropped, counts):
    return {"worklist": worklist, "dropped": dropped, "counts": counts}

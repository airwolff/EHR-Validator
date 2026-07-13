"""The nightly batch: the thing that actually runs the agents.

Pick up every record carrying a clinical note that hasn't been reviewed → ask each specialist
→ read the replies → throw out what isn't grounded in the note → save what survives → mark
the records reviewed. Offline by default: mode="replay" reads recorded answers and costs
nothing.

What these tests are really guarding:

- **A record is never half-reviewed.** The moment a record is stamped 'processed' it leaves
  the inbox forever. So if one specialist's reply is unreadable, the batch writes NOTHING —
  the records stay in the inbox and a retry re-asks. Half a review, permanently recorded as a
  whole one, is the worst outcome available here.
- **A cleared record still gets stamped.** Zero findings means "reviewed, nothing found", not
  "not reviewed yet" — otherwise the batch re-reads (and in live mode re-pays for) every clean
  record forever.
- **Every drop is counted.** Findings that quote text the note doesn't contain, and findings
  that name a record that wasn't in the batch, are the evidence the presentation rests on. A
  silent drop is a lost argument.
"""
import json

import pytest

from app.agents.batch import BatchAborted, run_nightly_batch
from app.agents.specialists import SPECIALISTS, build_message
from app.agents.transport import record_response
from tests.conftest import record_reply

NOTE = "62-year-old gentleman with history of BPH, here for follow-up. Afebrile, comfortable."

PAYLOAD = {
    "encounter": {"encounter_id": "E1"},
    "patient": {"patient_id": "P1", "sex": "F", "age": 34},
    "vitals": {"temp_f": 98.6},
    "clinical_note": NOTE,
}

# A finding whose quote really is in the note above.
GROUNDED = {
    "record_id": "E1", "field": "patient.sex",
    "problem": "Note describes a 62-year-old man; the record is a 34-year-old woman.",
    "severity": "critical", "adjudication": "Reconcile the note against the chart.",
    "evidence": "62-year-old gentleman with history of BPH",
    "confidence": "high", "remediation": "Route to HIM; likely copy-forward.", "owner": "him",
}

# Same shape, but the quote appears nowhere in the note — a fabrication.
HALLUCINATED = {
    **GROUNDED,
    "field": "vitals.temp_f",
    "problem": "Note says the patient is febrile.",
    "evidence": "patient is febrile at 103F",
}


def save_noted_record(store, payload=None):
    payload = payload or PAYLOAD
    return store.save_report(
        {"payload_id": payload["encounter"]["encounter_id"], "encounter_date": None,
         "status": "pass", "issue_count": 0, "issues": []},
        model="local", payload=payload)


def setup_batch(store, tmp_path, identity=(), clinical=(), payload=None):
    """One noted record in the store, and a recorded reply from each specialist."""
    run_id = save_noted_record(store, payload)
    records = store.get_noted_records()
    recordings = str(tmp_path / "recordings")
    record_reply(recordings, records, "identity", list(identity))
    record_reply(recordings, records, "clinical", list(clinical))
    return run_id, recordings


# --- the happy path, and the guard doing its job --------------------------------------

def test_a_grounded_finding_reaches_the_worklist(fresh_store, tmp_path):
    run_id, recordings = setup_batch(fresh_store, tmp_path, identity=[GROUNDED])

    result = run_nightly_batch("2026-07-13", mode="replay", recordings_dir=recordings)

    assert len(result["worklist"]) == 1
    finding = result["worklist"][0]
    assert finding["run_id"] == run_id
    assert finding["domain"] == "identity"
    assert finding["severity"] == "critical"


def test_a_fabricated_finding_is_dropped_and_counted(fresh_store, tmp_path):
    """The whole argument: the model cited text the chart never contained. It must not reach
    the worklist, and it must not vanish quietly either — the drop rate IS the evidence."""
    _, recordings = setup_batch(fresh_store, tmp_path, clinical=[HALLUCINATED])

    result = run_nightly_batch("2026-07-13", mode="replay", recordings_dir=recordings)

    assert result["worklist"] == []
    assert result["counts"]["dropped"] == 1
    assert result["counts"]["returned"] == 1
    dropped = result["dropped"][0]
    assert "evidence_not_in_note" in dropped["reasons"]
    assert dropped["finding"]["evidence"] == "patient is febrile at 103F"


def test_a_finding_about_a_record_that_was_not_in_the_batch_is_dropped_and_counted(
    fresh_store, tmp_path
):
    """Models invent record ids. A finding we cannot attribute must not be guessed onto some
    other patient — and it is not a hallucinated QUOTE, so it needs its own tally."""
    invented = {**GROUNDED, "record_id": "E-DOES-NOT-EXIST"}
    _, recordings = setup_batch(fresh_store, tmp_path, identity=[invented])

    result = run_nightly_batch("2026-07-13", mode="replay", recordings_dir=recordings)

    assert result["worklist"] == []
    assert result["counts"]["unknown_record"] == 1
    assert result["dropped"][0]["reasons"] == ["unknown_record_id"]


def test_the_specialist_decides_the_domain_and_owner_not_the_model(fresh_store, tmp_path):
    """We overwrite domain with the specialist's own name, so penalising the model for a bad
    domain would be penalising it on a field we throw away. Stamp first, then judge."""
    confused = {**GROUNDED, "domain": "billing", "owner": ""}
    _, recordings = setup_batch(fresh_store, tmp_path, identity=[confused])

    result = run_nightly_batch("2026-07-13", mode="replay", recordings_dir=recordings)

    assert len(result["worklist"]) == 1
    assert result["worklist"][0]["domain"] == "identity"
    assert result["worklist"][0]["owner"] == SPECIALISTS["identity"].default_owner
    assert result["counts"]["dropped"] == 0


# --- the inbox: processed exactly once ------------------------------------------------

def test_a_cleared_record_is_still_marked_reviewed(fresh_store, tmp_path):
    """Both agents found nothing. That is an ANSWER. If we don't stamp it, the record sits in
    the inbox forever and every future live run pays to be told 'nothing wrong' again."""
    _, recordings = setup_batch(fresh_store, tmp_path)

    result = run_nightly_batch("2026-07-13", mode="replay", recordings_dir=recordings)

    assert result["worklist"] == []
    assert fresh_store.get_noted_records() == [], "a cleared record was left in the inbox"


def test_a_reviewed_record_does_not_come_back_on_the_next_run(fresh_store, tmp_path):
    _, recordings = setup_batch(fresh_store, tmp_path, identity=[GROUNDED])

    run_nightly_batch("2026-07-13", mode="replay", recordings_dir=recordings)
    second = run_nightly_batch("2026-07-14", mode="replay", recordings_dir=recordings)

    assert second["counts"]["records"] == 0
    assert second["worklist"] == []
    # And the first run's finding was not written twice.
    assert len(fresh_store.get_worklist("2026-07-13")) == 1


def test_an_empty_inbox_is_not_an_error(fresh_store, tmp_path):
    result = run_nightly_batch("2026-07-13", mode="replay",
                               recordings_dir=str(tmp_path / "recordings"))
    assert result["worklist"] == []
    assert result["counts"]["records"] == 0


def test_running_twice_in_one_day_still_reports_that_days_findings(fresh_store, tmp_path):
    """Second run: the inbox is empty because the first run stamped everything. The worklist
    for the day has NOT changed — reporting [] would tell a demo audience the pipeline just
    lost their findings."""
    _, recordings = setup_batch(fresh_store, tmp_path, identity=[GROUNDED])

    first = run_nightly_batch("2026-07-13", mode="replay", recordings_dir=recordings)
    second = run_nightly_batch("2026-07-13", mode="replay", recordings_dir=recordings)

    assert len(first["worklist"]) == 1
    assert second["counts"]["records"] == 0        # nothing new to review
    assert len(second["worklist"]) == 1            # but the day's findings still stand
    assert second["worklist"] == first["worklist"]


def test_a_malformed_batch_date_is_refused_before_anything_is_written(fresh_store, tmp_path):
    """batch_date is the key the worklist is queried by. "2026-7-13" files the findings where
    nobody will ever look — and the records are stamped, so they never come back."""
    _, recordings = setup_batch(fresh_store, tmp_path, identity=[GROUNDED])

    for bad in ("2026-7-13", "13-07-2026", "yesterday", ""):
        with pytest.raises(ValueError):
            run_nightly_batch(bad, mode="replay", recordings_dir=recordings)

    assert len(fresh_store.get_noted_records()) == 1, "a bad date must not consume the inbox"


# --- failure: all or nothing ----------------------------------------------------------

def test_an_unreadable_reply_aborts_the_batch_and_writes_nothing(fresh_store, tmp_path):
    """The important one. If the clinical agent returns prose and we stamped the records
    anyway, those records leave the inbox with only HALF a review — permanently, and
    silently. Better to write nothing and let a retry re-ask."""
    store = fresh_store
    save_noted_record(store)
    records = store.get_noted_records()
    recordings = str(tmp_path / "recordings")
    record_reply(recordings, records, "identity", [GROUNDED])
    record_response(recordings, "clinical",
                    build_message(SPECIALISTS["clinical"], records),
                    "I'm sorry, I can't help with that.")

    with pytest.raises(BatchAborted):
        run_nightly_batch("2026-07-13", mode="replay", recordings_dir=recordings)

    assert store.get_worklist("2026-07-13") == [], "a half-reviewed batch was persisted"
    assert len(store.get_noted_records()) == 1, "the records must stay in the inbox for a retry"


def test_an_unreadable_reply_does_not_wedge_replay_forever(fresh_store, tmp_path):
    """The trap. A live call RECORDS the reply before anything tries to parse it. So a junk
    reply becomes a junk recording, and every offline run afterwards replays it and aborts
    again — the pipeline is permanently stuck and nothing says why. The batch must quarantine
    the recording it could not parse, and say so."""
    store = fresh_store
    save_noted_record(store)
    records = store.get_noted_records()
    recordings = str(tmp_path / "recordings")
    record_reply(recordings, records, "identity", [GROUNDED])
    message = build_message(SPECIALISTS["clinical"], records)
    record_response(recordings, "clinical", message, "I'm sorry, I can't help with that.")

    with pytest.raises(BatchAborted) as exc:
        run_nightly_batch("2026-07-13", mode="replay", recordings_dir=recordings)

    assert "quarantine" in str(exc.value).lower()
    # The poisoned recording is gone; a re-record (or a fixed one) can take its place.
    assert list((tmp_path / "recordings").glob("clinical-*.json")) == []
    assert list((tmp_path / "recordings").glob("*.rejected")), "the bad reply must be kept to look at"


def test_an_aborted_live_run_reports_what_it_spent(fresh_store, tmp_path, monkeypatch):
    """Task 13 needs 'the LLM cost N credits and returned unusable output in M runs'. Once the
    exception is raised, nobody can reconstruct the spend."""
    from app.agents.ledger import CreditLedger

    store = fresh_store
    save_noted_record(store)
    records = store.get_noted_records()
    recordings = str(tmp_path / "recordings")
    ledger = CreditLedger(str(tmp_path / "l.json"), budget=10, month="2026-07")

    replies = {"identity": json.dumps({"findings": [GROUNDED]}), "clinical": "I'm sorry."}
    monkeypatch.setattr("app.agents.transport.call_lyzr_live",
                        lambda agent_id, message: replies[
                            "identity" if "identity reviewer" in message else "clinical"])

    with pytest.raises(BatchAborted) as exc:
        run_nightly_batch("2026-07-13", mode="live", recordings_dir=recordings,
                          agent_id="agent-123", ledger=ledger)

    # The clinical specialist is asked first and is the one that fails, so the run stops after
    # ONE credit — it does not go on to ask the second specialist for a batch it will discard.
    assert exc.value.credits_spent == 1
    assert ledger.spent() == 1


def test_a_missing_recording_aborts_the_batch_and_writes_nothing(fresh_store, tmp_path):
    save_noted_record(fresh_store)

    with pytest.raises(FileNotFoundError):
        run_nightly_batch("2026-07-13", mode="replay",
                          recordings_dir=str(tmp_path / "no-recordings"))

    assert len(fresh_store.get_noted_records()) == 1


# --- money ----------------------------------------------------------------------------

def test_replay_mode_never_touches_the_network(fresh_store, tmp_path, monkeypatch):
    from app.agents import transport

    called = []
    monkeypatch.setattr(transport, "call_lyzr_live", lambda *a, **k: called.append(1))
    _, recordings = setup_batch(fresh_store, tmp_path, identity=[GROUNDED])

    run_nightly_batch("2026-07-13", mode="replay", recordings_dir=recordings)
    assert called == []


def test_live_mode_without_a_ledger_is_refused(fresh_store, tmp_path):
    from app.agents.transport import LiveCallRefused

    _, recordings = setup_batch(fresh_store, tmp_path, identity=[GROUNDED])
    with pytest.raises(LiveCallRefused):
        run_nightly_batch("2026-07-13", mode="live", recordings_dir=recordings,
                          agent_id="agent-123", ledger=None)

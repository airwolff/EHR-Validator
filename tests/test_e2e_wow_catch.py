"""End-to-end over the demo fixtures: ingest → rules → routing → agents → worklist.

Three tests, and together they are the whole presentation:

- **The wow catch.** Every structured field is valid — the rules find NOTHING — but the
  note describes a different person than the demographics. Only the identity agent can see
  that, which is exactly the claim the thesis makes about where an LLM belongs. Selection
  is on note-presence, so a zero-rule-issue record still reaches the agents. The note's
  CLINICAL content deliberately agrees with the structured diagnoses (hypertension, I10):
  a note contradicting the diagnosis list would invite a live clinical finding too, and
  the demo's "one finding, identity only" story would diverge from Task 12's real replies.
- **The false-positive guard.** A note that AGREES with the data must come back with zero
  findings — and the batch must still have SEEN the record (counts pin records: 1; without
  that, an ingest regression makes every assertion here pass with an empty inbox).
- **The mixed batch.** Both records at once, plus a finding that names the clean record
  while quoting the wow note. Attribution and the per-record evidence check only mean
  something when two records coexist — a judge-against-the-wrong-note bug is invisible to
  every single-record test in the suite.

The recorded replies are generated from the real ``build_message()`` output
(tests/conftest.py::record_reply) — recordings are keyed by a fingerprint of the exact
message, so a hand-authored recording would never be replayed.
"""
from tests.conftest import load_payload, record_reply

from app.agents.batch import run_nightly_batch
from app.router import route
from app.validator import LocalValidator

# What the identity agent says about the wow record. Authored here, not returned by a live
# model — Task 11 spends no credits. The evidence quote is verbatim from the payload's note,
# so it survives the evidence guard the way a real grounded reply would. `domain` and
# `owner` are deliberately ABSENT: the batch stamps both from the specialist, and authoring
# the stamped values here would let the assertions below pass even if the stamp broke.
WOW_FINDING = {
    "record_id": "E-WOW-01",
    "field": "patient.sex",
    "problem": "Note describes a 62-year-old man; the record is a 34-year-old woman.",
    "severity": "critical",
    "adjudication": "Reconcile the note against the chart demographics; likely copy-forward.",
    "evidence": "62-year-old gentleman with a history of hypertension",
    "confidence": "high",
    "remediation": "Route to HIM to confirm which patient this note belongs to.",
}

NO_DROPS = {"records": 1, "returned": 1, "kept": 1, "dropped": 0,
            "unknown_record": 0, "credits_spent": 0}


def ingest(store, name):
    """The same shape the real front door writes: validated, ROUTED, persisted with the
    payload and source_system — app/main.py's /validate and load_results.py both do this.
    Skipping route() here would write routing_domain=NULL rows production never produces
    (and /stats would silently omit them from the domain breakdown)."""
    payload = load_payload(name)
    report = LocalValidator().validate(payload)
    run_id = store.save_report(
        report, model="local",
        source_system=payload.get("metadata", {}).get("source_system"),
        routing=route(report), payload=payload)
    return report, run_id


def record_replies(tmp_path, store, replies):
    """Record each specialist's reply to the exact message this batch will send."""
    recordings = str(tmp_path / "recordings")
    records = store.get_noted_records()
    for name, findings in replies.items():
        record_reply(recordings, records, name, findings)
    return recordings


def test_wow_catch_passes_every_rule_but_the_identity_agent_flags_it(fresh_store, tmp_path):
    report, run_id = ingest(fresh_store, "payload_wrong_patient_note.json")

    # The rules find NOTHING — that is the point of the record. If this line fails the
    # payload has a structural defect and the demo argument collapses.
    assert report["issue_count"] == 0

    recordings = record_replies(tmp_path, fresh_store,
                                {"identity": [WOW_FINDING], "clinical": []})
    result = run_nightly_batch("2026-07-13", mode="replay", recordings_dir=recordings)

    assert len(result["worklist"]) == 1
    finding = result["worklist"][0]
    assert finding["run_id"] == run_id
    assert finding["domain"] == "identity"         # stamped by the batch, not authored above
    assert finding["owner"] == "him"               # ditto — the specialist's default owner
    assert finding["severity"] == "critical"
    assert "gentleman" in finding["evidence"]      # grounded in the real note
    assert result["counts"] == NO_DROPS


def test_clean_note_yields_no_findings_and_still_counts_as_reviewed(fresh_store, tmp_path):
    report, _ = ingest(fresh_store, "payload_note_clean.json")
    assert report["issue_count"] == 0              # clean structurally too

    recordings = record_replies(tmp_path, fresh_store, {"identity": [], "clinical": []})
    result = run_nightly_batch("2026-07-13", mode="replay", recordings_dir=recordings)

    assert result["worklist"] == []                # the false-positive guard
    # records: 1 is the load-bearing count — it proves the batch actually saw the record.
    # Without it, an ingest or note-selection regression takes the empty-inbox early return
    # and every other assertion in this test passes with the agents never consulted.
    assert result["counts"] == {"records": 1, "returned": 0, "kept": 0, "dropped": 0,
                                "unknown_record": 0, "credits_spent": 0}
    # "Nothing found" is an answer: the record is stamped and never re-read (or re-paid for).
    assert fresh_store.get_noted_records() == []


def test_mixed_batch_attributes_each_finding_to_its_own_record(fresh_store, tmp_path):
    """Both demo records in ONE batch — what the demo actually runs. The fabricated finding
    names the CLEAN record but quotes the WOW note: if the batch judged evidence against the
    wrong record's note it would sail through; judged against its own record's note it is a
    counted drop. No single-record test can catch that bug."""
    _, wow_run_id = ingest(fresh_store, "payload_wrong_patient_note.json")
    ingest(fresh_store, "payload_note_clean.json")

    cross_record = {**WOW_FINDING, "record_id": "E-CLEAN-01"}
    recordings = record_replies(tmp_path, fresh_store,
                                {"identity": [WOW_FINDING, cross_record], "clinical": []})
    result = run_nightly_batch("2026-07-13", mode="replay", recordings_dir=recordings)

    assert len(result["worklist"]) == 1
    assert result["worklist"][0]["run_id"] == wow_run_id
    dropped = result["dropped"][0]
    assert dropped["reasons"] == ["evidence_not_in_note"]
    assert dropped["finding"]["record_id"] == "E-CLEAN-01"
    assert result["counts"] == {"records": 2, "returned": 2, "kept": 1, "dropped": 1,
                                "unknown_record": 0, "credits_spent": 0}
    # Both records leave the inbox — the cleared one too, or it is re-paid for forever.
    assert fresh_store.get_noted_records() == []

"""Pins the agent-findings persistence layer.

Agent findings live in their own table, never mixed into validation_issues:
at demo time we must be able to say exactly which engine caught what.
"""

import pytest
from sqlalchemy import text


def _finding(domain="clinical", severity="warning", field="vitals.temp_f"):
    return {"domain": domain, "field": field, "problem": "x", "severity": severity,
            "adjudication": "a", "evidence": "e", "confidence": "high",
            "remediation": "r", "owner": "cdi"}


def _run_with_note(store, note, payload_id="E1"):
    report = {"payload_id": payload_id, "encounter_date": None, "status": "pass",
              "issue_count": 0, "issues": []}
    return store.save_report(report, model="local",
                             payload={"encounter": {"encounter_id": payload_id},
                                      "clinical_note": note})


def test_noted_records_selects_only_records_with_note(fresh_store):
    store = fresh_store
    _run_with_note(store, "patient alert")
    store.save_report({"payload_id": "E2", "encounter_date": None, "status": "pass",
                       "issue_count": 0, "issues": []}, model="local",
                      payload={"encounter": {"encounter_id": "E2"}})  # no note
    noted = store.get_noted_records()
    assert len(noted) == 1
    assert noted[0]["payload"]["clinical_note"] == "patient alert"


def test_findings_saved_and_worklist_sorted(fresh_store):
    store = fresh_store
    run_id = _run_with_note(store, "note")
    findings = [_finding(domain="clinical", severity="warning"),
                _finding(domain="identity", severity="critical", field="patient.sex")]

    assert store.record_agent_result(run_id, findings, batch_date="2026-07-09") == 2

    wl = store.get_worklist("2026-07-09")
    assert len(wl) == 2
    assert wl[0]["domain"] == "identity"   # identity precedence beats clinical
    assert wl[0]["run_id"] == run_id


def test_agent_findings_never_land_in_validation_issues(fresh_store):
    """The separation IS the presentation argument — guard it."""
    store = fresh_store
    run_id = _run_with_note(store, "note")
    store.record_agent_result(run_id, [_finding()], batch_date="2026-07-09")

    with store.engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM validation_issues")).scalar()
    assert n == 0


def test_recording_a_result_takes_the_record_out_of_the_inbox(fresh_store):
    store = fresh_store
    run_id = _run_with_note(store, "patient alert")
    assert len(store.get_noted_records()) == 1

    store.record_agent_result(run_id, [_finding()], batch_date="2026-07-13")
    assert store.get_noted_records() == []


def test_cleared_record_is_not_reoffered(fresh_store):
    """Why the marker exists: a record the agents CLEAR writes zero findings. Absence of
    findings must not read as 'not yet processed', or the batch re-reads — and re-pays
    for — every clean record forever."""
    store = fresh_store
    run_id = _run_with_note(store, "nothing wrong here")

    assert store.record_agent_result(run_id, [], batch_date="2026-07-13") == 0
    assert store.get_noted_records() == []


def test_findings_and_marker_commit_together(fresh_store):
    """Findings and the processed-marker are one transaction. If the write of a finding
    fails, the record must NOT be stamped — otherwise it leaves the inbox forever with
    its defects unreported."""
    store = fresh_store
    run_id = _run_with_note(store, "note")

    bad = _finding()
    del bad["severity"]                        # NOT NULL — the insert will blow up
    with pytest.raises(KeyError):
        store.record_agent_result(run_id, [_finding(), bad], batch_date="2026-07-13")

    with store.engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM agent_findings")).scalar()
    assert n == 0                              # the good finding rolled back too
    assert len(store.get_noted_records()) == 1  # and the record is still in the inbox


def test_unknown_run_id_is_loud_not_silent(fresh_store):
    store = fresh_store
    with pytest.raises(ValueError, match="does not exist"):
        store.record_agent_result(9999, [_finding()], batch_date="2026-07-13")


def test_worklist_is_scoped_to_its_batch_date(fresh_store):
    store = fresh_store
    run_a = _run_with_note(store, "note", payload_id="E1")
    run_b = _run_with_note(store, "note", payload_id="E2")

    store.record_agent_result(run_a, [_finding()], batch_date="2026-07-09")
    store.record_agent_result(run_b, [_finding()], batch_date="2026-07-10")

    assert len(store.get_worklist("2026-07-09")) == 1
    assert len(store.get_worklist("2026-07-10")) == 1


def test_worklist_ties_hold_insertion_order(fresh_store):
    """Two findings tied on (domain, severity) must not reshuffle between runs."""
    store = fresh_store
    run_id = _run_with_note(store, "note")
    store.record_agent_result(run_id, [
        _finding(field="first"), _finding(field="second"), _finding(field="third"),
    ], batch_date="2026-07-13")

    wl = store.get_worklist("2026-07-13")
    assert [f["field"] for f in wl] == ["first", "second", "third"]


def test_admin_domain_is_ranked_not_silently_last(fresh_store):
    """`admin` is a domain router.py really emits. Leaving it out of the order map sorts
    it below every known domain with no warning — the Task 3 labs skew, again."""
    store = fresh_store
    assert "admin" in store.WORKLIST_DOMAIN_ORDER


def test_non_dict_payload_does_not_kill_the_batch(fresh_store):
    """One malformed row must not take down the inbox for every other record."""
    store = fresh_store
    store.save_report({"payload_id": "BAD", "encounter_date": None, "status": "pass",
                       "issue_count": 0, "issues": []}, model="local",
                      payload=["not", "an", "object"])
    good = _run_with_note(store, "patient alert", payload_id="E2")

    noted = store.get_noted_records()
    assert [n["run_id"] for n in noted] == [good]

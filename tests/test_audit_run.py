"""tests/test_audit_run.py"""
import json
import os
import tempfile

import pytest


@pytest.fixture()
def env(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{os.path.join(tmp, 'test.db')}")
    import importlib
    from app import store as store_module
    store = importlib.reload(store_module)
    store.init_db()
    payload = {"patient": {"age": 50, "sex": "F", "race": "Black", "zip": None},
               "metadata": {"source_system": "MEDITECH"},
               "encounter": {"encounter_date": "2026-06-20"},
               "clinical_note": "50-year-old woman presents with chest pain. "
                                "Patient appears anxious."}
    store.save_report({"payload_id": "P-A", "encounter_date": "2026-06-20",
                       "status": "pass", "issue_count": 0, "issues": []},
                      model="local", source_system="MEDITECH", payload=payload)
    store.save_demographics([store.demographics_from_payload("P-A", payload)])
    recordings = os.path.join(tmp, "recordings")
    os.makedirs(recordings)
    return store, recordings


def _record_reply(store, recordings, reply):
    from app.agents import audit
    from app.agents.transport import record_response
    message = audit.build_audit_message(
        store.get_audit_aggregates("2026-06"), store.get_month_corpus("2026-06"))
    record_response(recordings, "auditor", message, reply)


GOOD_REPLY = json.dumps({"patterns": [{
    "name": "gender tone bias", "severity": "warning",
    "evidence": [{"record_id": "P-A", "quote": "appears anxious"}],
    "hypothesis": "female chest-pain notes use dismissive language",
    "recommended_action": "audit documentation templates"}]})


def test_replay_run_persists_and_returns_counts(env):
    store, recordings = env
    from app.agents import audit
    _record_reply(store, recordings, GOOD_REPLY)
    result = audit.run_month_end_audit("2026-06", mode="replay",
                                       recordings_dir=recordings)
    assert result["counts"] == {"records": 1, "patterns_returned": 1,
                                "patterns_kept": 1, "evidence_dropped": 0,
                                "credits_spent": 0}
    from sqlalchemy import text
    with store.engine.connect() as conn:
        report = conn.execute(text("SELECT * FROM audit_reports")).mappings().one()
        pattern = conn.execute(text("SELECT * FROM audit_patterns")).mappings().one()
    assert report["report_month"] == "2026-06" and report["patterns_kept"] == 1
    assert pattern["name"] == "gender tone bias"
    assert json.loads(pattern["evidence_json"])[0]["record_id"] == "P-A"


def test_rerun_replaces_not_duplicates(env):
    store, recordings = env
    from app.agents import audit
    _record_reply(store, recordings, GOOD_REPLY)
    audit.run_month_end_audit("2026-06", mode="replay", recordings_dir=recordings)
    audit.run_month_end_audit("2026-06", mode="replay", recordings_dir=recordings)
    from sqlalchemy import text
    with store.engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) AS n FROM audit_reports")).mappings().one()
    assert n["n"] == 1


def test_unparseable_reply_quarantines_and_raises(env):
    store, recordings = env
    from app.agents import audit
    _record_reply(store, recordings, "So sorry, no JSON today!")
    with pytest.raises(audit.AuditAborted):
        audit.run_month_end_audit("2026-06", mode="replay", recordings_dir=recordings)
    assert any(p.endswith(".rejected") for p in os.listdir(recordings))
    from sqlalchemy import text
    with store.engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) AS n FROM audit_reports")).mappings().one()
    assert n["n"] == 0   # nothing persisted on abort


def test_bad_month_key_refused(env):
    store, recordings = env
    from app.agents import audit
    with pytest.raises(ValueError):
        audit.run_month_end_audit("2026-6", mode="replay", recordings_dir=recordings)


def test_empty_month_refused(env):
    store, recordings = env
    from app.agents import audit
    with pytest.raises(ValueError):
        audit.run_month_end_audit("2025-01", mode="replay", recordings_dir=recordings)

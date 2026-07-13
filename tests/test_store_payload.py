import importlib
import json

import pytest
from sqlalchemy import text


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A fresh store bound to a throwaway SQLite file, not the demo DB."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path/'t.db'}")
    import app.store as store
    importlib.reload(store)
    store.init_db()
    yield store
    importlib.reload(store)   # restore the module for other tests


def _report(payload_id="E1"):
    return {"payload_id": payload_id, "encounter_date": None, "status": "pass",
            "issue_count": 0, "issues": []}


def _payload_json(store, run_id):
    with store.engine.connect() as c:
        row = c.execute(text("SELECT payload_json FROM validation_runs WHERE run_id=:r"),
                        {"r": run_id}).mappings().one()
    return row["payload_json"]


def test_payload_is_persisted(store):
    payload = {"encounter": {"encounter_id": "E1"}, "clinical_note": "hello"}
    run_id = store.save_report(_report(), model="local", payload=payload)
    assert json.loads(_payload_json(store, run_id))["clinical_note"] == "hello"


def test_payload_round_trips_intact(store):
    """The nightly agent batch re-reads this; it must survive byte-for-byte in meaning."""
    payload = {"encounter": {"encounter_id": "E1"}, "clinical_note": "pt is 34wks pregnant",
               "labs": [{"test": "CBC", "value": None, "ordered": True, "resulted": False}],
               "vitals": {"temp_f": 71.2}}
    run_id = store.save_report(_report(), model="local", payload=payload)
    assert json.loads(_payload_json(store, run_id)) == payload


def test_saving_without_a_payload_still_works(store):
    """Existing callers pass no payload; they must not break."""
    run_id = store.save_report(_report(), model="local")
    assert _payload_json(store, run_id) is None


def test_bulk_load_persists_payload_and_routing(store):
    """The bulk loader is how records reach the DB; the nightly agent batch reads
    payload_json back out of it, and /stats groups by routing_domain. If the bulk
    path drops either, both are silently empty."""
    payload = {"encounter": {"encounter_id": "E1"}, "clinical_note": "hello"}
    routing = {"domain": "clinical", "escalated": True, "reason": "critical vital"}
    store.save_reports_bulk([(_report(), "epic", routing, payload)], model="local")

    with store.engine.connect() as c:
        row = c.execute(text(
            "SELECT payload_json, routing_domain, escalated FROM validation_runs"
        )).mappings().one()

    assert json.loads(row["payload_json"])["clinical_note"] == "hello"
    assert row["routing_domain"] == "clinical"
    assert row["escalated"] == 1

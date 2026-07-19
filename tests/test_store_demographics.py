"""tests/test_store_demographics.py"""
import os
import tempfile

import pytest


@pytest.fixture()
def fresh_store(monkeypatch):
    # Same isolation pattern as the existing store tests: point DATABASE_URL at a
    # temp SQLite file and re-import store bindings onto a fresh engine.
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{os.path.join(tmp, 'test.db')}")
    import importlib
    from app import store as store_module
    store = importlib.reload(store_module)
    store.init_db()
    yield store


def _payload(pid="P-1", race="White", zip_code="04849"):
    return {
        "patient": {"patient_id": pid, "age": 40, "sex": "F", "race": race, "zip": zip_code},
        "metadata": {"source_system": "Epic"},
    }


def test_demographics_from_payload_extracts_the_audit_fields(fresh_store):
    d = fresh_store.demographics_from_payload("P-1", _payload())
    assert d == {"payload_id": "P-1", "age": 40, "sex": "F", "race": "White",
                 "zip": "04849", "source_system": "Epic"}


def test_demographics_from_payload_missing_fields_become_none(fresh_store):
    d = fresh_store.demographics_from_payload("P-2", {"patient": {}, "metadata": {}})
    assert d["race"] is None and d["zip"] is None and d["source_system"] is None


def test_save_demographics_is_idempotent_per_payload_id(fresh_store):
    row = fresh_store.demographics_from_payload("P-1", _payload())
    fresh_store.save_demographics([row])
    fresh_store.save_demographics([{**row, "zip": None}])  # reload with a change
    from sqlalchemy import text
    with fresh_store.engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT payload_id, zip FROM record_demographics")).mappings().all()
    assert len(rows) == 1 and rows[0]["zip"] is None

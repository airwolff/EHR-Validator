"""tests/test_store_audit_reads.py"""
import os
import tempfile

import pytest


@pytest.fixture()
def loaded_store(monkeypatch):
    tmp = tempfile.mkdtemp()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{os.path.join(tmp, 'test.db')}")
    import importlib
    from app import store as store_module
    store = importlib.reload(store_module)
    store.init_db()
    payloads = {
        "P-A": {"patient": {"age": 50, "sex": "F", "race": "Black", "zip": None},
                "metadata": {"source_system": "MEDITECH"},
                "encounter": {"encounter_date": "2026-06-20"},
                "clinical_note": "note A"},
        "P-B": {"patient": {"age": 60, "sex": "M", "race": "White", "zip": "04915"},
                "metadata": {"source_system": "Epic"},
                "encounter": {"encounter_date": "2026-06-02"},
                "clinical_note": "note B"},
        "P-C": {"patient": {"age": 30, "sex": "F", "race": "White", "zip": "04841"},
                "metadata": {"source_system": "Epic"},
                "encounter": {"encounter_date": "2026-05-30"},   # NOT June
                "clinical_note": "note C"},
    }
    for pid, payload in payloads.items():
        report = {"payload_id": pid, "encounter_date": payload["encounter"]["encounter_date"],
                  "status": "fail" if pid == "P-A" else "pass",
                  "issue_count": 1 if pid == "P-A" else 0,
                  "issues": ([{"field": "vitals.temp_f", "problem": "implausible",
                               "severity": "warning", "remediation": "recheck"}]
                             if pid == "P-A" else [])}
        store.save_report(report, model="local",
                          source_system=payload["metadata"]["source_system"],
                          payload=payload)
        store.save_demographics([store.demographics_from_payload(pid, payload)])
    yield store


def test_month_corpus_scopes_and_sorts(loaded_store):
    corpus = loaded_store.get_month_corpus("2026-06")
    assert [c["payload_id"] for c in corpus] == ["P-A", "P-B"]   # P-C is May
    assert corpus[0]["note"] == "note A"
    assert corpus[0]["demographics"]["race"] == "Black"


def test_aggregates_shape_and_determinism(loaded_store):
    a1 = loaded_store.get_audit_aggregates("2026-06")
    a2 = loaded_store.get_audit_aggregates("2026-06")
    assert a1 == a2
    assert a1["month"] == "2026-06"
    assert a1["top_failing_fields"] == [{"field": "vitals.temp_f", "issues": 1}]
    systems = {s["source_system"]: s for s in a1["issues_by_source_system"]}
    assert systems["MEDITECH"]["issues"] == 1 and systems["Epic"]["issues"] == 0
    zip_by_race = {r["race"]: r for r in a1["missing_zip_by_race"]}
    assert zip_by_race["Black"]["missing_zip"] == 1
    assert zip_by_race["White"]["missing_zip"] == 0

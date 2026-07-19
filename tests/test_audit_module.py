"""tests/test_audit_module.py"""
import pytest

from app.agents import audit
from app.agents.specialists import ResponseUnparseable


CORPUS = [
    {"payload_id": "P-A", "demographics": {"age": 50, "sex": "F", "race": "Black",
                                           "zip": None, "source_system": "MEDITECH"},
     "note": "50-year-old woman presents with chest pain. Patient appears anxious."},
    {"payload_id": "P-B", "demographics": {"age": 60, "sex": "M", "race": "White",
                                           "zip": "04915", "source_system": "Epic"},
     "note": "60-year-old man presents with chest pain. Cardiac workup ordered."},
]
AGG = {"month": "2026-06", "top_failing_fields": [{"field": "vitals.temp_f", "issues": 9}],
       "issues_by_source_system": [], "missing_zip_by_race": []}


def test_message_is_pure_and_order_independent():
    m1 = audit.build_audit_message(AGG, CORPUS)
    m2 = audit.build_audit_message(AGG, list(reversed(CORPUS)))
    assert m1 == m2
    assert "AGGREGATES:" in m1 and "RECORDS:" in m1 and "P-A" in m1


def _pattern(**over):
    p = {"name": "gender tone bias", "severity": "warning",
         "evidence": [{"record_id": "P-A", "quote": "appears anxious"},
                      {"record_id": "P-B", "quote": "Cardiac workup ordered"}],
         "hypothesis": "female chest-pain notes use dismissive language",
         "recommended_action": "audit documentation templates"}
    p.update(over)
    return p


def _sources():
    src = {c["payload_id"]: c["note"] for c in CORPUS}
    src[audit.AGGREGATES_ID] = audit.aggregates_text(AGG)
    return src


def test_grounded_pattern_survives():
    kept, dropped = audit.ground_patterns([_pattern()], _sources())
    assert len(kept) == 1 and dropped == []


def test_fabricated_quote_drops_evidence_and_is_counted():
    p = _pattern(evidence=[{"record_id": "P-A", "quote": "appears anxious"},
                           {"record_id": "P-A", "quote": "totally invented words"}])
    kept, dropped = audit.ground_patterns([p], _sources())
    assert len(kept) == 1 and len(kept[0]["evidence"]) == 1
    assert len(dropped) == 1 and "evidence_not_in_note" in dropped[0]["reasons"]


def test_pattern_with_no_surviving_evidence_drops_whole():
    p = _pattern(evidence=[{"record_id": "P-X", "quote": "appears anxious"}])
    kept, dropped = audit.ground_patterns([p], _sources())
    assert kept == []
    assert any("unknown_record_id" in d["reasons"] for d in dropped)


def test_aggregates_are_a_valid_evidence_source():
    p = _pattern(evidence=[{"record_id": audit.AGGREGATES_ID,
                            "quote": '"issues": 9'}])
    kept, _ = audit.ground_patterns([p], _sources())
    assert len(kept) == 1


def test_malformed_pattern_drops():
    kept, dropped = audit.ground_patterns([_pattern(severity="banana")], _sources())
    assert kept == [] and "malformed" in dropped[0]["reasons"]


def test_parse_tolerates_fences_and_raises_on_prose():
    raw = '```json\n{"patterns": [' + str(_pattern()).replace("'", '"') + ']}\n```'
    assert len(audit.parse_audit_report(raw)) == 1
    with pytest.raises(ResponseUnparseable):
        audit.parse_audit_report("I could not find any patterns, sorry!")

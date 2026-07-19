"""tests/test_audit_grading.py"""
import json
from pathlib import Path

from app.agents.audit_grading import grade_patterns

KEY = json.loads((Path(__file__).resolve().parents[1]
                  / "scripts" / "audit_answer_key.json").read_text())


def _p(name, hypothesis):
    return {"name": name, "severity": "warning", "evidence": [],
            "hypothesis": hypothesis, "recommended_action": "review"}


def test_caught_partial_missed():
    kept = [
        _p("MEDITECH temperature unit error",
           "MEDITECH began sending Celsius values in the Fahrenheit field mid-month; "
           "a unit conversion is being skipped."),
        _p("note wording", "some notes mention zip codes"),   # 1 term hit on race key
    ]
    grades = {g["planted_key"]: g["outcome"] for g in grade_patterns(kept, KEY)}
    assert grades["unit_conversion_meditech"] == "caught"
    assert grades["race_missing_zip"] == "partial"
    assert grades["copy_paste_note"] == "missed"
    assert grades["gender_tone_bias"] == "missed"


def test_term_matching_is_case_insensitive_and_word_bounded():
    kept = [_p("bias check", "Female patients' notes show a dismissive TONE.")]
    grades = {g["planted_key"]: g["outcome"] for g in grade_patterns(kept, KEY)}
    assert grades["gender_tone_bias"] == "caught"

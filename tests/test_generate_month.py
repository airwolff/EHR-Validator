"""tests/test_generate_month.py"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "generate_month.py"
KEY = Path(__file__).resolve().parents[1] / "scripts" / "audit_answer_key.json"


@pytest.fixture(scope="module")
def month_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("month")
    subprocess.run([sys.executable, str(SCRIPT), "--out", str(out)], check=True)
    return out


def _records(d):
    return {p.name: json.loads(p.read_text()) for p in sorted(d.glob("payload_M*.json"))}


def test_generator_is_deterministic(month_dir, tmp_path):
    again = tmp_path / "again"
    subprocess.run([sys.executable, str(SCRIPT), "--out", str(again)], check=True)
    assert _records(month_dir) == _records(again)


def test_forty_records_all_in_june(month_dir):
    recs = _records(month_dir)
    assert len(recs) == 40
    assert all(r["encounter"]["encounter_date"].startswith("2026-06-")
               for r in recs.values())


def test_planted_unit_conversion(month_dir):
    celsius = [r for r in _records(month_dir).values()
               if r["metadata"]["source_system"] == "MEDITECH"
               and r["encounter"]["encounter_date"] >= "2026-06-15"
               and 34.0 <= r["vitals"]["temp_f"] <= 41.0]
    assert len(celsius) >= 5  # the symptom spike SQL will see


def test_planted_tone_pairs(month_dir):
    notes = [r["clinical_note"] for r in _records(month_dir).values()]
    dismissive = [n for n in notes if "anxious" in n and "insists" in n]
    workup = [n for n in notes if "workup" in n]
    assert len(dismissive) >= 4 and len(workup) >= 4


def test_planted_race_missingness(month_dir):
    recs = list(_records(month_dir).values())
    def missing_zip_rate(race):
        group = [r for r in recs if r["patient"].get("race") == race]
        return sum(1 for r in group if not r["patient"].get("zip")) / len(group)
    assert missing_zip_rate("Black") >= 0.5
    assert missing_zip_rate("White") <= 0.15


def test_answer_key_collision_guard(month_dir):
    """Planted tone phrases must not leak into ordinary notes, or grading is ambiguous."""
    recs = _records(month_dir).values()
    ordinary = [r["clinical_note"] for r in recs
                if "chest pain" not in r["clinical_note"].lower()]
    assert all("poor historian" not in n for n in ordinary)
    key = json.loads(KEY.read_text())
    assert key["report_month"] == "2026-06" and len(key["planted"]) == 4

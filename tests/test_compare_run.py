# tests/test_compare_run.py
"""The whole experiment end-to-end, offline: authored recordings in, graded rows in a
throwaway DB out. Pins the two behaviors that differ from the nightly batch: an
unreadable reply is a COUNTED data point (not an abort), and re-running replaces rows
(not duplicates)."""
import copy
import os

import pytest

from app.agents import compare
from app.agents.transport import record_response, recording_path
from tests.conftest import record_compare_reply


@pytest.fixture
def payloads(payload_loader):
    return {rid: payload_loader(rid + ".json")
            for rid in compare.CANONICAL_RECORD_IDS}


def _perfect_findings(key):
    return [
        {"record_id": rid, "field": issue["field"], "problem": issue["problem"],
         "severity": issue["severity"], "remediation": issue.get("remediation") or "fix"}
        for rid, issues in key.items()
        for issue in issues.values()
    ]


@pytest.fixture
def three_recorded_tries(tmp_path, payloads):
    """Try 1: flawless. Try 2: one miss, one misgrade, one false alarm. Try 3: junk."""
    rec = str(tmp_path / "recordings")
    key = compare.answer_key(payloads)

    record_compare_reply(rec, 1, payloads, _perfect_findings(key))

    flawed = copy.deepcopy(_perfect_findings(key))
    flawed = [f for f in flawed if f["field"] != "vitals.spo2_pct"]
    for f in flawed:
        if f["field"] == "vitals.temp_f":
            f["severity"] = "warning"
    flawed.append({"record_id": "payload_clean", "field": "vitals.temp_f",
                   "problem": "made up", "severity": "warning", "remediation": "none"})
    record_compare_reply(rec, 2, payloads, flawed)

    record_response(rec, compare.SPECIALIST_NAME,
                    compare.build_comparison_message(3, payloads),
                    "I'm sorry, I can't help with these records.")
    return rec


def test_experiment_end_to_end(fresh_store, three_recorded_tries, payloads):
    result = compare.run_comparison(3, mode="replay",
                                    recordings_dir=three_recorded_tries)

    assert result["usable_runs"] == 2
    assert result["unusable_runs"] == 1
    assert result["runs"][0]["counts"] == {
        "caught": 15, "severity_mismatch": 0, "missed": 0, "false_alarm": 0}
    assert result["runs"][1]["counts"] == {
        "caught": 13, "severity_mismatch": 1, "missed": 1, "false_alarm": 1}
    assert result["runs"][2]["usable"] is False
    assert result["totals"]["missed"] == 1

    # the junk reply is quarantined so it can never poison a future replay
    bad_path = recording_path(three_recorded_tries, compare.SPECIALIST_NAME,
                              compare.build_comparison_message(3, payloads))
    assert not os.path.exists(bad_path)
    assert os.path.exists(bad_path + ".rejected")

    # and the DB agrees with the return value
    from sqlalchemy import text
    with fresh_store.engine.connect() as conn:
        runs = conn.execute(text(
            "SELECT * FROM comparison_runs ORDER BY run_number")).mappings().all()
        n_results = conn.execute(text(
            "SELECT COUNT(*) FROM comparison_results")).scalar()
    assert len(runs) == 3
    assert [r["usable"] for r in runs] == [1, 1, 0]
    assert n_results == 15 + 16  # try 1: 15 rows; try 2: 15 + 1 false alarm; try 3: none


def test_rerunning_replay_replaces_rows_not_duplicates(fresh_store, three_recorded_tries):
    compare.run_comparison(2, mode="replay", recordings_dir=three_recorded_tries)
    compare.run_comparison(2, mode="replay", recordings_dir=three_recorded_tries)
    from sqlalchemy import text
    with fresh_store.engine.connect() as conn:
        n_runs = conn.execute(text("SELECT COUNT(*) FROM comparison_runs")).scalar()
    assert n_runs == 2


def test_missing_recording_stops_with_filenotfound(fresh_store, tmp_path):
    with pytest.raises(FileNotFoundError):
        compare.run_comparison(1, mode="replay",
                               recordings_dir=str(tmp_path / "empty"))


def test_quarantined_recording_replays_as_unusable_not_crash(fresh_store, tmp_path, payloads):
    """A junk reply we already paid for gets quarantined once; replaying the whole
    experiment afterwards must keep reporting it unusable, not raise FileNotFoundError
    (the recording is gone — renamed to .rejected — after the first quarantine)."""
    rec = str(tmp_path / "recordings")
    message = compare.build_comparison_message(1, payloads)
    record_response(rec, compare.SPECIALIST_NAME, message,
                    "I'm sorry, I can't help with these records.")

    first = compare.run_comparison(1, mode="replay", recordings_dir=rec)
    assert first["runs"][0]["usable"] is False
    assert first["unusable_runs"] == 1

    bad_path = recording_path(rec, compare.SPECIALIST_NAME, message)
    assert not os.path.exists(bad_path)
    assert os.path.exists(bad_path + ".rejected")

    second = compare.run_comparison(1, mode="replay", recordings_dir=rec)
    assert second["runs"][0]["usable"] is False
    assert second["unusable_runs"] == 1
    assert "quarantined" in second["runs"][0]["error"]

    from sqlalchemy import text
    with fresh_store.engine.connect() as conn:
        runs = conn.execute(text(
            "SELECT * FROM comparison_runs WHERE run_number = 1 AND mode = 'replay'"
        )).mappings().all()
    assert len(runs) == 1
    assert runs[0]["usable"] == 0


def test_dropped_junk_findings_are_counted_on_the_run_row(fresh_store, tmp_path, payloads):
    rec = str(tmp_path / "recordings")
    record_compare_reply(rec, 1, payloads, [
        {"record_id": "payload_clean", "field": "x", "problem": "p",
         "severity": "banana", "remediation": "r"}])
    result = compare.run_comparison(1, mode="replay", recordings_dir=rec)
    assert result["runs"][0]["dropped_findings"] == 1
    from sqlalchemy import text
    with fresh_store.engine.connect() as conn:
        run = conn.execute(text("SELECT * FROM comparison_runs")).mappings().one()
    assert run["dropped_findings"] == 1

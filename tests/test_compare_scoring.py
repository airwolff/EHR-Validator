"""The grader: rules are the answer key, code does the grading, and the four outcomes
(caught / severity_mismatch / missed / false_alarm) are pinned by planted examples."""
import copy

import pytest

from app.agents import compare


@pytest.fixture
def key(payload_loader):
    payloads = {rid: payload_loader(rid + ".json")
                for rid in compare.CANONICAL_RECORD_IDS}
    return compare.answer_key(payloads)


def _perfect_findings(key):
    """What a flawless AI reply would look like: one finding per answer-key problem."""
    return [
        {"record_id": rid, "field": issue["field"], "problem": issue["problem"],
         "severity": issue["severity"], "remediation": issue.get("remediation") or "fix"}
        for rid, issues in key.items()
        for issue in issues.values()
    ]


def test_answer_key_drift_guard_15_problems_today(key):
    """If a fixture or rule quietly changes, this goes red INSTEAD of the experiment
    silently grading against a different answer key."""
    assert sum(len(issues) for issues in key.values()) == 15
    assert key["payload_clean"] == {}  # the clean record really is clean


def test_perfect_reply_grades_all_caught(key):
    results = compare.score_run(_perfect_findings(key), key)
    assert compare.tally(results) == {
        "caught": 15, "severity_mismatch": 0, "missed": 0, "false_alarm": 0}


def test_planted_miss_misgrade_and_false_alarm_each_grade(key):
    findings = copy.deepcopy(_perfect_findings(key))
    findings = [f for f in findings if f["field"] != "vitals.spo2_pct"]  # planted miss
    for f in findings:
        if f["field"] == "vitals.temp_f":
            f["severity"] = "warning"                       # planted misgrade
    findings.append({"record_id": "payload_clean", "field": "vitals.temp_f",
                     "problem": "made up", "severity": "warning",
                     "remediation": "none"})                # planted false alarm
    results = compare.score_run(findings, key)
    assert compare.tally(results) == {
        "caught": 13, "severity_mismatch": 1, "missed": 1, "false_alarm": 1}
    missed = [r for r in results if r["outcome"] == "missed"]
    assert missed == [{"record_id": "payload_bad_values", "field": "vitals.spo2_pct",
                       "rule_severity": "critical", "llm_severity": None,
                       "outcome": "missed"}]
    false = [r for r in results if r["outcome"] == "false_alarm"]
    assert false[0]["record_id"] == "payload_clean"
    assert false[0]["rule_severity"] is None


def test_bracket_and_dot_field_spellings_count_as_the_same(key):
    finding = {"record_id": "payload_bad_codes", "field": "diagnoses.0.code",
               "problem": "bad code", "severity": "critical", "remediation": "fix"}
    results = compare.score_run([finding], key)
    caught = [r for r in results if r["outcome"] == "caught"]
    assert len(caught) == 1
    assert caught[0]["field"] == "diagnoses[0].code"  # the rules' spelling is stored


def test_junk_findings_are_dropped_and_counted_not_graded():
    kept, dropped = compare.partition_comparison_findings(
        [
            {"record_id": "payload_clean", "field": "x", "problem": "p",
             "severity": "banana", "remediation": "r"},        # invented severity
            {"record_id": "someone_else", "field": "x", "problem": "p",
             "severity": "info", "remediation": "r"},          # unknown record
            {"record_id": "payload_clean", "field": "", "problem": "p",
             "severity": "info", "remediation": "r"},          # empty required value
            "not even a dict",
        ],
        set(compare.CANONICAL_RECORD_IDS))
    assert kept == []
    assert len(dropped) == 4


def test_duplicate_findings_on_one_field_grade_once(key):
    """Two findings on the same field must not double-count: if EITHER has the right
    severity the problem was caught."""
    f1 = {"record_id": "payload_bad_values", "field": "vitals.spo2_pct",
          "problem": "impossible", "severity": "warning", "remediation": "fix"}
    f2 = dict(f1, severity="critical")
    results = compare.score_run([f1, f2], key)
    spo2 = [r for r in results if r["field"] == "vitals.spo2_pct"]
    assert len(spo2) == 1
    assert spo2[0]["outcome"] == "caught"

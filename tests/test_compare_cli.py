"""The CLI prints JSON on success and one readable 'comparison refused:' line on a
deliberate refusal — a missing recording must not be a stack trace."""
import json

import pytest

from app.agents import compare
from tests.conftest import record_compare_reply


def test_cli_replay_prints_the_summary(fresh_store, tmp_path, payload_loader, capsys):
    payloads = {rid: payload_loader(rid + ".json")
                for rid in compare.CANONICAL_RECORD_IDS}
    key = compare.answer_key(payloads)
    perfect = [
        {"record_id": rid, "field": i["field"], "problem": i["problem"],
         "severity": i["severity"], "remediation": i.get("remediation") or "fix"}
        for rid, issues in key.items() for i in issues.values()
    ]
    rec = str(tmp_path / "recordings")
    record_compare_reply(rec, 1, payloads, perfect)

    compare.main(["--runs", "1", "--mode", "replay", "--recordings", rec])

    out = json.loads(capsys.readouterr().out)
    assert out["usable_runs"] == 1
    assert out["totals"]["missed"] == 0


def test_cli_refuses_in_one_line_when_nothing_is_recorded(fresh_store, tmp_path):
    with pytest.raises(SystemExit) as exc:
        compare.main(["--runs", "1", "--mode", "replay",
                      "--recordings", str(tmp_path / "empty")])
    assert "comparison refused" in str(exc.value)


def test_cli_caps_runs_at_the_permutation_count(fresh_store, tmp_path):
    with pytest.raises(SystemExit) as exc:
        compare.main(["--runs", "6", "--mode", "replay",
                      "--recordings", str(tmp_path / "empty")])
    assert "comparison refused" in str(exc.value)
    # Pin the CAP refusal specifically — an empty recordings dir also refuses, and
    # without this line the test passes even with the pre-loop guard deleted.
    assert "1..5, got 6" in str(exc.value)

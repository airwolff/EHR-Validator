"""The demo entrypoint: `python -m app.agents --date ... --mode replay|live`.

Prints the whole batch result — see run_nightly_batch's docstring for why the counts
matter — and turns deliberate refusals (no agent id, no budget, junk date) into one-line
exits instead of tracebacks.
"""
import json

import pytest

from tests.conftest import record_reply, save_noted_record

NOTE = "Note describes a 62-year-old gentleman with a history of BPH."

PAYLOAD = {"encounter": {"encounter_id": "E1"},
           "patient": {"patient_id": "P1", "sex": "F", "age": 34},
           "clinical_note": NOTE}

FINDING = {"record_id": "E1", "field": "patient.sex",
           "problem": "Note describes a man; the record is a 34-year-old woman.",
           "severity": "critical",
           "adjudication": "Reconcile the note against the chart.",
           "evidence": "62-year-old gentleman",
           "confidence": "high", "remediation": "Route to HIM."}


def test_replay_cli_prints_worklist_and_counts(fresh_store, tmp_path, capsys):
    from app.agents.__main__ import main

    save_noted_record(fresh_store, PAYLOAD)
    recordings = str(tmp_path / "recordings")
    records = fresh_store.get_noted_records()
    record_reply(recordings, records, "identity", [FINDING])
    record_reply(recordings, records, "clinical", [])

    main(["--date", "2026-07-13", "--mode", "replay", "--recordings", recordings])

    out = json.loads(capsys.readouterr().out)
    assert len(out["worklist"]) == 1
    assert out["worklist"][0]["domain"] == "identity"
    assert out["counts"] == {"records": 1, "returned": 1, "kept": 1, "dropped": 0,
                             "unknown_record": 0, "credits_spent": 0}


def test_an_unreadable_reply_is_a_one_line_refusal_not_a_traceback(fresh_store, tmp_path):
    """Seen live on 2026-07-14: the identity agent returned broken JSON and the operator
    got a wall of traceback instead of BatchAborted's own 'run it again' message."""
    from app.agents.__main__ import main
    from app.agents.specialists import SPECIALISTS, build_message
    from app.agents.transport import record_response

    save_noted_record(fresh_store, PAYLOAD)
    recordings = str(tmp_path / "recordings")
    records = fresh_store.get_noted_records()
    record_reply(recordings, records, "identity", [FINDING])
    record_response(recordings, "clinical",
                    build_message(SPECIALISTS["clinical"], records),
                    "I'm sorry, I can't help with that.")

    with pytest.raises(SystemExit, match="could not be read"):
        main(["--date", "2026-07-13", "--mode", "replay", "--recordings", recordings])


def test_live_cli_without_an_agent_id_is_a_one_line_refusal(fresh_store, tmp_path, monkeypatch):
    """The live branch's wiring, without any network: the CLI must build the ledger (a
    typo'd mode condition would pass None and lean on nothing) and transport's
    no-agent-id refusal must surface as a clean exit, not a traceback."""
    from app.agents.__main__ import main

    monkeypatch.setenv("LYZR_AGENT_ID", "")
    monkeypatch.setenv("LYZR_BATCH_AGENT_ID", "")
    monkeypatch.setenv("LYZR_CREDIT_BUDGET", "5")
    monkeypatch.setenv("LYZR_LEDGER_PATH", str(tmp_path / "ledger.json"))
    save_noted_record(fresh_store, PAYLOAD)

    with pytest.raises(SystemExit, match="agent_id"):
        main(["--date", "2026-07-13", "--mode", "live",
              "--recordings", str(tmp_path / "recordings")])

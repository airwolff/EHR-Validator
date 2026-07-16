"""The record/replay seam.

Calling Lyzr costs real credits. So the FIRST time we ask the agent something we save its
answer to a file; every run after that reads the file instead of the network. "Record" =
save the answer. "Replay" = read it back.

Two rules this file exists to enforce:

1. **A saved answer belongs to the question that produced it.** File it under the agent's
   name AND a fingerprint of what we asked. Ask something we never recorded and the code
   must STOP — not hand back the answer to a different question, which would staple one
   patient's findings onto another patient's record.
2. **Nothing here touches the network.** The single live-call function is monkeypatched in
   every test below. If the suite ever needs Wi-Fi, this seam has failed.
"""
import json
import os

import pytest

from app.agents import transport
from app.agents.ledger import BudgetExceeded, CreditLedger
from app.agents.transport import (
    LiveCallFailed,
    LiveCallRefused,
    MissingCredentials,
    Replayer,
    TransportError,
    fingerprint,
    get_response,
    record_response,
)

ANSWER = '{"findings": [{"field": "vitals.temp_f"}]}'


def ledger(tmp_path, budget=5):
    return CreditLedger(str(tmp_path / "ledger.json"), budget=budget, month="2026-07")


# --- record and replay ----------------------------------------------------------------

def test_a_recorded_answer_replays(tmp_path):
    d = str(tmp_path)
    record_response(d, "clinical", "chart for patient A", ANSWER)
    assert Replayer(d).response_for("clinical", "chart for patient A") == ANSWER


def test_replaying_a_question_we_never_recorded_raises(tmp_path):
    """The whole point of the fingerprint. Patient A's answer must not be served for
    Patient B's chart just because the same specialist produced it."""
    d = str(tmp_path)
    record_response(d, "clinical", "chart for patient A", ANSWER)
    with pytest.raises(FileNotFoundError):
        Replayer(d).response_for("clinical", "chart for patient B")


def test_two_specialists_asked_the_same_question_do_not_collide(tmp_path):
    d = str(tmp_path)
    record_response(d, "clinical", "same chart", '{"findings": ["clinical"]}')
    record_response(d, "identity", "same chart", '{"findings": ["identity"]}')
    assert Replayer(d).response_for("clinical", "same chart") == '{"findings": ["clinical"]}'
    assert Replayer(d).response_for("identity", "same chart") == '{"findings": ["identity"]}'


def test_the_recording_keeps_the_question_so_a_human_can_read_it(tmp_path):
    """The filename is a fingerprint and unreadable by design; the file itself must not be."""
    d = str(tmp_path)
    record_response(d, "clinical", "chart for patient A", ANSWER)
    saved = json.loads(next(tmp_path.glob("clinical-*.json")).read_text())
    assert saved["specialist"] == "clinical"
    assert saved["message"] == "chart for patient A"
    assert saved["response"] == ANSWER


def test_the_same_question_always_gets_the_same_fingerprint(tmp_path):
    assert fingerprint("chart A") == fingerprint("chart A")
    assert fingerprint("chart A") != fingerprint("chart B")


def test_re_recording_the_same_question_overwrites_rather_than_piles_up(tmp_path):
    d = str(tmp_path)
    record_response(d, "clinical", "chart A", '{"findings": []}')
    record_response(d, "clinical", "chart A", ANSWER)
    assert Replayer(d).response_for("clinical", "chart A") == ANSWER
    assert len(list(tmp_path.glob("clinical-*.json"))) == 1


def test_recordings_are_written_atomically(tmp_path):
    """A crash mid-write must not leave a half-file that later reads as a corrupt recording."""
    record_response(str(tmp_path), "clinical", "chart A", ANSWER)
    assert [f for f in os.listdir(tmp_path) if f.startswith(".tmp-")] == []


def test_a_recording_filed_under_the_wrong_name_is_caught_not_served(tmp_path):
    """Belt and braces. The fingerprint decides WHICH file to open; the question stored
    INSIDE the file proves it is the right one. Without this check the guarantee rests on
    the filename alone — and filenames get hand-copied, and truncated hashes can collide."""
    d = str(tmp_path)
    record_response(d, "clinical", "chart for patient A", ANSWER)
    # Simulate a mis-filed recording: patient A's answer under patient B's fingerprint.
    misfiled = tmp_path / f"clinical-{fingerprint('chart for patient B')}.json"
    misfiled.write_text(json.dumps(
        {"specialist": "clinical", "message": "chart for patient A", "response": ANSWER}))

    with pytest.raises(TransportError):
        Replayer(d).response_for("clinical", "chart for patient B")


def test_a_malformed_recording_says_so_instead_of_raising_keyerror(tmp_path):
    d = str(tmp_path)
    path = tmp_path / f"clinical-{fingerprint('chart A')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"specialist": "clinical", "message": "chart A"}))  # no answer
    with pytest.raises(TransportError) as exc:
        Replayer(d).response_for("clinical", "chart A")
    assert str(path) in str(exc.value)


# --- get_response: replay mode --------------------------------------------------------

def test_replay_mode_returns_the_recording_and_never_calls_lyzr(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(transport, "call_lyzr_live", lambda *a, **k: called.append(1))
    d = str(tmp_path)
    record_response(d, "identity", "chart A", ANSWER)
    out = get_response("identity", "chart A", mode="replay", recordings_dir=d)
    assert out == ANSWER
    assert called == []


def test_an_unknown_mode_is_refused(tmp_path):
    with pytest.raises(ValueError):
        get_response("clinical", "chart A", mode="sideways", recordings_dir=str(tmp_path))


# --- get_response: live mode ----------------------------------------------------------

def test_live_mode_spends_one_credit_calls_lyzr_and_records_the_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(transport, "call_lyzr_live", lambda agent_id, message: ANSWER)
    d = str(tmp_path / "recordings")
    led = ledger(tmp_path, budget=5)

    out = get_response("clinical", "chart A", mode="live", recordings_dir=d,
                       agent_id="agent-123", ledger=led)

    assert out == ANSWER
    assert led.spent() == 1
    # And the point of recording: the same question is now free forever.
    assert Replayer(d).response_for("clinical", "chart A") == ANSWER


def test_live_mode_without_a_ledger_is_refused_before_any_call(tmp_path, monkeypatch):
    """ledger=None must not mean 'no cap'. An unbudgeted live path is how you wake up to a
    bill: a stray EHR_ENGINE=lyzr and a loop is all it takes."""
    called = []
    monkeypatch.setattr(transport, "call_lyzr_live", lambda *a, **k: called.append(1))
    with pytest.raises(LiveCallRefused):
        get_response("clinical", "chart A", mode="live",
                     recordings_dir=str(tmp_path), agent_id="agent-123", ledger=None)
    assert called == []


def test_live_mode_without_an_agent_id_is_refused_before_spending(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(transport, "call_lyzr_live", lambda *a, **k: called.append(1))
    led = ledger(tmp_path)
    with pytest.raises(LiveCallRefused):
        get_response("clinical", "chart A", mode="live", recordings_dir=str(tmp_path),
                     agent_id=None, ledger=led)
    assert called == []
    assert led.spent() == 0


def test_an_over_budget_ledger_stops_the_call_before_it_happens(tmp_path, monkeypatch):
    """The credit is charged BEFORE the network call, so a refusal costs nothing. The
    reverse order would let a runaway loop spend the whole budget and only then notice."""
    called = []
    monkeypatch.setattr(transport, "call_lyzr_live", lambda *a, **k: called.append(1))
    led = ledger(tmp_path, budget=1)
    led.spend()

    with pytest.raises(BudgetExceeded):
        get_response("clinical", "chart A", mode="live", recordings_dir=str(tmp_path),
                     agent_id="agent-123", ledger=led)
    assert called == [], "the ledger let a call through after the budget was gone"


def test_a_failed_live_call_records_nothing(tmp_path, monkeypatch):
    """Half a transaction is worse than none: a recording of a failure would replay forever
    as if it were the agent's real answer."""
    def boom(agent_id, message):
        raise RuntimeError("lyzr said 500")

    monkeypatch.setattr(transport, "call_lyzr_live", boom)
    d = str(tmp_path / "recordings")
    with pytest.raises(RuntimeError):
        get_response("clinical", "chart A", mode="live", recordings_dir=d,
                     agent_id="agent-123", ledger=ledger(tmp_path))
    assert not os.path.exists(d) or os.listdir(d) == []


# --- the live client itself (still no network) ----------------------------------------

def test_a_failed_call_reports_the_http_status_so_it_can_be_diagnosed_without_paying_again(
    monkeypatch,
):
    """'The call failed' is useless at 1 credit per retry: 401 (wrong key), 404 (wrong agent
    id) and 429 (rate limited) need different fixes. The status code carries no secret."""
    import urllib.error

    def unauthorized(request, timeout=None):
        raise urllib.error.HTTPError(
            url="https://lyzr", code=401, msg="Unauthorized", hdrs=None, fp=None)

    monkeypatch.setenv("LYZR_API_KEY", "sk-secret-do-not-leak")
    monkeypatch.setattr(transport.urllib.request, "urlopen", unauthorized)

    with pytest.raises(LiveCallFailed) as exc:
        transport.call_lyzr_live("agent-123", "chart A")
    assert "401" in str(exc.value)
    assert "sk-secret-do-not-leak" not in str(exc.value)


def test_the_recordings_directory_can_be_moved_by_env_var(tmp_path, monkeypatch):
    """On Render the app's own folder is wiped on every deploy — a recording we PAID for
    would vanish. The location has to be settable from outside, like DATABASE_URL."""
    monkeypatch.setenv("LYZR_RECORDINGS_DIR", str(tmp_path / "elsewhere"))
    assert transport.recordings_dir() == str(tmp_path / "elsewhere")


def test_a_missing_api_key_is_a_clear_error_not_a_keyerror(monkeypatch):
    monkeypatch.delenv("LYZR_API_KEY", raising=False)
    with pytest.raises(MissingCredentials):
        transport.call_lyzr_live("agent-123", "chart A")


def test_the_api_key_never_appears_in_an_error_message(monkeypatch):
    """A traceback ends up in logs, in a screenshot, in a slide. The key was rotated once
    after an exposure already."""
    monkeypatch.setenv("LYZR_API_KEY", "sk-secret-do-not-leak")
    monkeypatch.setenv("LYZR_AGENT_URL", "http://127.0.0.1:9/never-listens")
    with pytest.raises(Exception) as exc:
        transport.call_lyzr_live("agent-123", "chart A")
    assert "sk-secret-do-not-leak" not in str(exc.value)


# ---------------------------------------------------------------------------
# The timeout knob (added after the first Task-13 live run hit the hardcoded
# 60s with the credit already spent — a too-short timeout costs real money).
# ---------------------------------------------------------------------------

def test_timeout_defaults_to_60_when_env_unset(monkeypatch):
    monkeypatch.delenv(transport.TIMEOUT_ENV_VAR, raising=False)
    assert transport._timeout_seconds() == transport.DEFAULT_TIMEOUT_SECONDS


def test_timeout_env_override_is_used(monkeypatch):
    monkeypatch.setenv(transport.TIMEOUT_ENV_VAR, "240")
    assert transport._timeout_seconds() == 240.0


def test_timeout_junk_or_nonpositive_refuses(monkeypatch):
    for bad in ("abc", "0", "-5"):
        monkeypatch.setenv(transport.TIMEOUT_ENV_VAR, bad)
        with pytest.raises(LiveCallRefused):
            transport._timeout_seconds()


def test_live_mode_refuses_a_junk_timeout_before_spending(tmp_path, monkeypatch):
    """A typo'd LYZR_TIMEOUT_SECONDS must cost nothing: the refusal fires with the
    ledger untouched and the network never called."""
    called = []
    monkeypatch.setattr(transport, "call_lyzr_live", lambda *a, **k: called.append(1))
    monkeypatch.setenv(transport.TIMEOUT_ENV_VAR, "not-a-number")
    led = ledger(tmp_path)
    with pytest.raises(LiveCallRefused):
        get_response("clinical", "chart A", mode="live", recordings_dir=str(tmp_path),
                     agent_id="agent-123", ledger=led)
    assert called == []
    assert led.spent() == 0

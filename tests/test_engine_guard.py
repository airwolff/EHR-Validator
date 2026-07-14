"""A stray EHR_ENGINE=lyzr must hit the credit ledger BEFORE anything can touch the network.

The charge lives inside LyzrValidator.validate itself — not in any caller — so every path
to Lyzr (the /validate endpoint, load_results.py --engine lyzr, a hand-constructed
validator) is gated identically. Ordering matters twice over: free config checks come
FIRST (a refusal must cost nothing), and the charge comes BEFORE the network call
(charging after lets a runaway loop outrun the cap).

Every lyzr-engined test here points LYZR_AGENT_URL at an unroutable local port: even if
the guard broke entirely, nothing in this file can reach the real endpoint. Not
theoretical — an earlier version of this file watched the unguarded path fail and spent a
real credit doing it, because the developer's .env carries working credentials.
"""
import importlib

import pytest

from app.agents.ledger import BudgetExceeded, CreditLedger

PAYLOAD = {"encounter": {"encounter_id": "E1"}, "metadata": {}}

# Well-formed but fake: the config checks must PASS so the tests reach the spend, and the
# unroutable URL guarantees a broken guard fails locally instead of calling Lyzr.
FAKE_CREDS = {"LYZR_API_KEY": "test-key", "LYZR_AGENT_ID": "test-agent",
              "LYZR_AGENT_URL": "http://127.0.0.1:9"}


@pytest.fixture
def main_with_env():
    """Reload app.main under a controlled environment, and RESTORE it afterwards.

    app.main reads EHR_ENGINE at import time, so changing the engine means reloading the
    module. The MonkeyPatch context undoes every env var — no hand-maintained key list to
    forget one in — and only then does the final reload rebuild app.main from the pristine
    environment; reloading first would bake the test env into the module and leak a
    lyzr-engined app.main into every later-collected test."""
    import app.main as main

    with pytest.MonkeyPatch.context() as mp:
        def _reload(**env):
            for key, value in env.items():
                mp.setenv(key, value)
            importlib.reload(main)
            return main

        yield _reload
    importlib.reload(main)


def test_lyzr_engine_is_blocked_when_the_budget_is_spent(tmp_path, main_with_env, fresh_store):
    main = main_with_env(EHR_ENGINE="lyzr", LYZR_CREDIT_BUDGET="0",
                         LYZR_LEDGER_PATH=str(tmp_path / "ledger.json"), **FAKE_CREDS)

    with pytest.raises(BudgetExceeded):
        main.validate(PAYLOAD)


def test_a_permitted_call_charges_exactly_one_credit_then_proceeds(
    tmp_path, main_with_env, fresh_store
):
    """The failure shape the budget-0 test cannot see: a guard that CHECKS the budget but
    never charges it. Prove the spend was recorded (the ledger reads exactly 1) and that
    the request then went on to the network leg (the unroutable URL fails there)."""
    from app.agents.transport import LiveCallFailed

    ledger_file = tmp_path / "ledger.json"
    main = main_with_env(EHR_ENGINE="lyzr", LYZR_CREDIT_BUDGET="5",
                         LYZR_LEDGER_PATH=str(ledger_file), **FAKE_CREDS)

    with pytest.raises(LiveCallFailed):
        main.validate(PAYLOAD)

    assert CreditLedger(str(ledger_file), budget=5).spent() == 1


def test_an_unconfigured_lyzr_engine_refuses_before_charging(
    tmp_path, main_with_env, fresh_store
):
    """Config checks are free, per transport's rule. A mis-deployed server (engine set,
    key forgotten) must NOT record a phantom spend per failed request — fifteen 500s
    would brick the month's budget without one real credit leaving Lyzr."""
    ledger_file = tmp_path / "ledger.json"
    main = main_with_env(EHR_ENGINE="lyzr", LYZR_CREDIT_BUDGET="5",
                         LYZR_LEDGER_PATH=str(ledger_file),
                         LYZR_API_KEY="", LYZR_AGENT_ID="")

    with pytest.raises(RuntimeError, match="not configured"):
        main.validate(PAYLOAD)

    assert not ledger_file.exists(), "a refused call must cost nothing"


def test_local_engine_never_consults_the_ledger(tmp_path, main_with_env, fresh_store):
    """A corrupt ledger must block LIVE calls only; if the local path so much as reads
    it, a bad ledger file takes down the whole API."""
    corrupt = tmp_path / "ledger.json"
    corrupt.write_text("not json at all")
    main = main_with_env(EHR_ENGINE="local", LYZR_LEDGER_PATH=str(corrupt))

    response = main.validate(PAYLOAD)

    assert response.status_code == 200


def test_budget_exhaustion_is_an_http_429_not_a_500(tmp_path, main_with_env, fresh_store):
    """The refusal is the spend gate WORKING. A client must be able to tell 'budget cap,
    by design' from 'server crashed', and the ledger's actionable message must reach them
    — not die in a stderr traceback as an anonymous Internal Server Error."""
    from fastapi.testclient import TestClient

    main = main_with_env(EHR_ENGINE="lyzr", LYZR_CREDIT_BUDGET="0",
                         LYZR_LEDGER_PATH=str(tmp_path / "ledger.json"), **FAKE_CREDS)
    client = TestClient(main.app, raise_server_exceptions=False)

    response = client.post("/validate", json=PAYLOAD)

    assert response.status_code == 429
    assert "budget" in response.json()["detail"].lower()

import importlib
import json
import os

import pytest

# Tracked test data. The generated payloads/ dir at the repo root stays gitignored,
# so tests must not read from it — a fresh clone has no payloads/ until the generator runs.
PAYLOAD_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "payloads")


def load_payload(name: str) -> dict:
    with open(os.path.join(PAYLOAD_DIR, name), "r") as f:
        return json.load(f)


@pytest.fixture
def payload_loader():
    return load_payload


@pytest.fixture
def fresh_store(tmp_path, monkeypatch):
    """app.store reloaded onto a throwaway SQLite db, and RESTORED afterwards.

    app/store.py builds its engine at import time from DATABASE_URL, so pointing a test
    at a temp db means reloading the module — in place, which is why app.agents.batch's
    `from app import store` reference sees it too. The restore reload matters just as
    much: without it the module stays bound to a deleted tmp db for every later-collected
    test, an order-dependent flake that passes today only because each store-touching test
    file happens to reload first. The env var is undone BEFORE the restore reload —
    monkeypatch's own teardown runs after fixture finalizers, too late to matter.
    """
    import app.store as store
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    importlib.reload(store)
    store.init_db()
    yield store
    monkeypatch.delenv("DATABASE_URL")
    importlib.reload(store)


def record_reply(recordings_dir, records, specialist_name, findings):
    """Record what `specialist_name` would say about exactly these records.

    Built from the real build_message() output — recordings are keyed by a fingerprint
    of the exact message (see app/agents/transport.py), so a hand-authored recording
    would never be replayed.
    """
    from app.agents.specialists import SPECIALISTS, build_message
    from app.agents.transport import record_response

    message = build_message(SPECIALISTS[specialist_name], records)
    record_response(recordings_dir, specialist_name, message,
                    json.dumps({"findings": findings}))

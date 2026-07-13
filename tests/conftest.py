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

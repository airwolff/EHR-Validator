"""The record/replay seam — the ONLY place in this codebase that talks to Lyzr.

Every live call costs a real credit. So the first time we ask a specialist agent something,
we save its answer to a file; from then on the pipeline reads the file instead of the
network. Tests, demos and re-runs cost nothing, run offline, and give the same answer twice
— which is also what makes the Task-13 rules-vs-LLM comparison reproducible.

**A saved answer belongs to the question that produced it.** Recordings are filed under the
specialist AND a fingerprint of the exact message we sent (a fingerprint = a short string
derived from the text; the same text always produces the same one, different text almost
never does). Filing by specialist alone — as the plan originally had it — means a run over
records you never recorded silently gets back the answer to somebody else's question, and
because every finding must quote its own patient's note (see schema.py), the guard would
then throw those findings out as fabricated. The drop rate the presentation reports would be
measuring our own bug. Better to stop with FileNotFoundError and say "no recording for this
input".

The filename is unreadable on purpose, so the file itself is not: each recording stores the
question, the answer, and when it was taken.

Live mode fails closed, twice over: no ledger means REFUSED (not "unlimited"), and the
credit is charged BEFORE the call, so a refusal costs nothing and a runaway loop hits the
cap instead of the bill.
"""
import hashlib
import json
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime

from app.agents._fileio import atomic_write_text

DEFAULT_URL = "https://agent-prod.studio.lyzr.ai/v3/inference/chat/"

# A hung socket with no timeout blocks the batch forever — the process just sits there and
# the credit is already spent. Fail loudly instead.
DEFAULT_TIMEOUT_SECONDS = 60

TIMEOUT_ENV_VAR = "LYZR_TIMEOUT_SECONDS"


def _timeout_seconds():
    """How long to wait for Lyzr's answer. Overridable via LYZR_TIMEOUT_SECONDS.

    Added after the first Task-13 live run: the comparison message (5 full records,
    ~15 findings asked for) hit the hardcoded 60s and the credit was already spent —
    a too-short timeout costs real money, so its length belongs in .env, not code.
    A junk value refuses BEFORE the ledger is charged, same fail-closed rule as the
    ledger's own budget parsing."""
    raw = os.environ.get(TIMEOUT_ENV_VAR)
    if raw is None or not raw.strip():
        return DEFAULT_TIMEOUT_SECONDS
    try:
        timeout = float(raw)
    except ValueError:
        raise LiveCallRefused(
            f"{TIMEOUT_ENV_VAR}={raw!r} is not a number. Refusing to guess a timeout."
        ) from None
    if timeout <= 0:
        raise LiveCallRefused(f"{TIMEOUT_ENV_VAR}={raw!r} must be positive.")
    return timeout

_DEFAULT_RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "recordings")


def recordings_dir():
    """Where recordings live. Overridable, because the default is inside the package and on
    Render that filesystem is wiped on every deploy — a recording we spent a credit on would
    silently vanish. Same pattern as DATABASE_URL and LYZR_LEDGER_PATH."""
    return os.environ.get("LYZR_RECORDINGS_DIR", _DEFAULT_RECORDINGS_DIR)


class TransportError(RuntimeError):
    """Base for every reason a live call could not be made or completed."""


class LiveCallRefused(TransportError):
    """We declined to call Lyzr — the caller's setup would have been unsafe."""


class MissingCredentials(TransportError):
    """LYZR_API_KEY (or the agent id) is not set."""


class LiveCallFailed(TransportError):
    """Lyzr was called and the call did not succeed."""


def fingerprint(message):
    """A short, stable id for a message. Same text in, same id out."""
    return hashlib.sha256(message.encode("utf-8")).hexdigest()[:12]


def recording_path(recordings_dir, specialist, message):
    return os.path.join(recordings_dir, f"{specialist}-{fingerprint(message)}.json")


class Replayer:
    """Reads saved answers back. Never touches the network."""

    def __init__(self, recordings_dir):
        self.dir = recordings_dir

    def response_for(self, specialist, message):
        """The recorded answer to exactly this question, or FileNotFoundError.

        Refusing an unrecorded question is the feature: the alternative is answering it with
        a different question's answer, and being wrong quietly."""
        path = recording_path(self.dir, specialist, message)
        try:
            with open(path) as f:
                saved = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"No recording for specialist {specialist!r} with this exact message "
                f"(expected {path}). Record it with mode='live' — that spends a credit."
            ) from None
        except json.JSONDecodeError as exc:
            raise TransportError(f"Recording {path} is not readable JSON ({exc}).") from exc

        if not isinstance(saved, dict) or "response" not in saved:
            raise TransportError(
                f"Recording {path} has no 'response' — it is malformed, not empty. "
                f"Delete it and re-record, or fix it by hand."
            )
        # The fingerprint chose WHICH file to open; the question stored inside proves it is
        # the right one. Without this, the whole guarantee rests on a 12-character filename
        # that can be hand-copied or (vanishingly rarely) collide — and the failure it would
        # produce is exactly the one this design exists to prevent: one patient's answer
        # served for another patient's chart, silently.
        if saved.get("message") != message:
            raise TransportError(
                f"Recording {path} answers a DIFFERENT question than the one asked. "
                f"Refusing to serve it. Delete it and re-record."
            )
        return saved["response"]


def quarantine_recording(recordings_dir, specialist, message):
    """Move a recording aside so it stops being replayed. Returns the new path, or None.

    A live call records the reply BEFORE anything tries to parse it — which is right (an
    honest record of what the agent actually said), but it means a junk reply becomes a junk
    recording, and every offline run afterwards replays the junk and fails again. The pipeline
    would be permanently wedged with no hint as to why. Renaming it to .rejected takes it out
    of the replay path while keeping it on disk to look at: it is evidence, not garbage."""
    path = recording_path(recordings_dir, specialist, message)
    if not os.path.exists(path):
        return None
    rejected = path + ".rejected"
    os.replace(path, rejected)
    return rejected


def record_response(recordings_dir, specialist, message, raw):
    """Save an agent's answer alongside the question that produced it."""
    atomic_write_text(
        recording_path(recordings_dir, specialist, message),
        json.dumps(
            {
                "specialist": specialist,
                "message": message,
                "response": raw,
                "recorded_at": datetime.now().isoformat(timespec="seconds"),
            },
            indent=2,
        ),
    )


def call_lyzr_live(agent_id, message):
    """The one function in this codebase that spends money. Never called by the tests."""
    api_key = os.environ.get("LYZR_API_KEY")
    if not api_key:
        raise MissingCredentials("LYZR_API_KEY is not set — cannot make a live call.")

    endpoint = os.environ.get("LYZR_AGENT_URL", DEFAULT_URL)
    body = json.dumps({
        "user_id": os.environ.get("LYZR_USER_ID", "default_user"),
        "agent_id": agent_id,
        "session_id": f"{agent_id}-{uuid.uuid4()}",
        "message": message,
    }).encode()
    request = urllib.request.Request(endpoint, data=body, headers={
        "Content-Type": "application/json",
        "accept": "application/json",
        "x-api-key": api_key,
    })

    try:
        with urllib.request.urlopen(request, timeout=_timeout_seconds()) as response:
            raw = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        # The status code is what tells you WHICH fix you need — 401 wrong key, 404 wrong
        # agent_id, 429 rate limited, 5xx their problem — and at one credit per retry,
        # guessing is expensive. The code and reason carry no secret; the Request headers do,
        # so they are never interpolated (see below).
        raise LiveCallFailed(
            f"Live Lyzr call to {endpoint} failed: HTTP {exc.code} {exc.reason}"
        ) from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        # Deliberately does NOT chain the original exception (`from None`) and never
        # interpolates the request: urllib puts the failing Request — headers and all — into
        # some errors, and the header carries the API key. A traceback ends up in logs, in a
        # screenshot, on a slide. This key has been rotated after an exposure once already.
        raise LiveCallFailed(f"Live Lyzr call to {endpoint} failed: {type(exc).__name__}") from None

    # Lyzr has changed this field name before; accept the known spellings, else hand back the
    # whole body rather than silently returning nothing.
    for key in ("agent_response", "response", "message", "answer"):
        if isinstance(raw, dict) and key in raw:
            return raw[key]
    return json.dumps(raw)


def get_response(specialist, message, *, mode, recordings_dir, agent_id=None, ledger=None):
    """Ask a specialist. mode='replay' reads a saved answer; mode='live' spends a credit.

    `message` MUST be a pure function of the records — same records in, byte-identical text
    out. It is fingerprinted to find the recording, so anything that varies run to run (a
    timestamp, a uuid, an unsorted dict) changes the fingerprint, and then NO replay ever
    hits: the offline path breaks, and a live batch re-pays for records it already recorded.
    Whatever builds the message is responsible for this; see specialists.build_message.

    The credit is charged BEFORE the network call, so a failed call still costs one. That is
    deliberate — charging afterwards means a runaway loop can spend the entire budget before
    the ledger ever hears about it, and the ledger's only job is to make that impossible.
    Losing a credit to a Lyzr 500 is the cheaper mistake. Do not reorder these.
    """
    if mode == "replay":
        return Replayer(recordings_dir).response_for(specialist, message)

    if mode == "live":
        # Both checks happen BEFORE the ledger is charged and before the network is touched.
        if ledger is None:
            raise LiveCallRefused(
                "Live mode requires a CreditLedger. Refusing to call Lyzr with no spend cap."
            )
        if not agent_id:
            raise LiveCallRefused("Live mode requires an agent_id (set LYZR_AGENT_ID).")
        # Validate the timeout NOW, while refusing is still free — call_lyzr_live reads
        # it again after the charge, and a typo'd .env value must not cost a credit.
        _timeout_seconds()

        ledger.spend(1)  # raises BudgetExceeded, and then no call happens at all
        raw = call_lyzr_live(agent_id, message)
        # Only a successful call is recorded. Recording a failure would replay forever as if
        # it were the agent's real answer.
        record_response(recordings_dir, specialist, message, raw)
        return raw

    raise ValueError(f"Unknown mode {mode!r} — use 'replay' or 'live'.")

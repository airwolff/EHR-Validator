"""The batch's front door: python -m app.agents --date 2026-07-13 [--mode replay|live]

Prints the whole batch result as JSON — worklist, dropped findings, and the counts that
run_nightly_batch's docstring explains. replay (the default) reads recorded answers and
costs nothing. live spends real credits: it requires LYZR_AGENT_ID (and LYZR_API_KEY) in
the environment, and it always runs through the credit ledger — there is deliberately no
flag to switch the ledger off.
"""
import argparse
import json
import os

# The CLI is run from a plain shell, so it loads .env itself (same pattern as
# app/validator.py). Without this, LYZR_API_KEY/LYZR_BATCH_AGENT_ID only exist
# if the operator remembered to export them.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.agents.batch import BatchAborted, run_nightly_batch
from app.agents.ledger import CreditLedger, LedgerError, ledger_path
from app.agents.transport import TransportError, recordings_dir


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m app.agents",
        description="Run the nightly agent batch over every unreviewed noted record.")
    parser.add_argument("--date", required=True,
                        help="Batch date, YYYY-MM-DD. The key the worklist is filed under.")
    parser.add_argument("--mode", choices=["replay", "live"], default="replay",
                        help="replay = recorded answers, free (default). "
                             "live = real Lyzr calls; spends credits, records the replies.")
    parser.add_argument("--recordings", default=recordings_dir(),
                        help="Recordings directory (default: %(default)s).")
    args = parser.parse_args(argv)

    try:
        # Budget and ledger location both resolve inside the ledger, so the CLI and the
        # validator path can never disagree about the cap. Replay gets no ledger at all —
        # the offline path must keep working even when the ledger file is corrupt.
        ledger = CreditLedger(ledger_path()) if args.mode == "live" else None
        result = run_nightly_batch(
            args.date,
            mode=args.mode,
            recordings_dir=args.recordings,
            # The batch's agent is a plain instruction-follower (the specialist prompt
            # rides inside each message). LYZR_AGENT_ID — the Phase-1 validator agent,
            # which has its own baked-in instructions — is only the fallback so a
            # single-agent setup still runs.
            agent_id=(os.environ.get("LYZR_BATCH_AGENT_ID")
                      or os.environ.get("LYZR_AGENT_ID")),
            ledger=ledger,
        )
    except (BatchAborted, LedgerError, TransportError, ValueError) as exc:
        # Deliberate refusals (unreadable reply, budget, credentials, malformed date),
        # not crashes. In a cron log a one-line refusal and a traceback are very
        # different mornings. BatchAborted's message already says what to do next.
        raise SystemExit(f"batch refused: {exc}") from exc
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

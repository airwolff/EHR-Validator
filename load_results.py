"""
Process payloads through a validator and persist to SQLite.

Loads the bulk dataset (payloads/encounters.jsonl) if present; otherwise falls
back to the individual canonical payload_*.json fixtures.

Usage:
  python3 load_results.py                  # local validator (default)
  python3 load_results.py --engine lyzr    # deployed Lyzr agent (must be configured)
  python3 load_results.py --fixtures       # force-load the 5 canonical fixtures instead of bulk
"""

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from app.validator import get_validator
from app.router import route
from app.store import init_db, save_report, save_reports_bulk


def load_bulk(validator, path):
    items = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            report = validator.validate(payload)
            source = payload.get("metadata", {}).get("source_system")
            items.append((report, source, route(report), payload))
    save_reports_bulk(items, model=validator.name)
    passed = sum(1 for r, _ in items if r["status"] == "pass")
    return len(items), passed


def load_fixtures(validator, payload_dir):
    files = sorted(glob.glob(os.path.join(payload_dir, "payload_*.json")))
    for path in files:
        with open(path) as f:
            payload = json.load(f)
        report = validator.validate(payload)
        source = payload.get("metadata", {}).get("source_system")
        routing = route(report)
        run_id = save_report(report, model=validator.name, source_system=source,
                             routing=routing, payload=payload)
        print(f"  {os.path.basename(path):32s} -> {report['status']:4s}  "
              f"({report['issue_count']} issue(s))  {routing['domain']:8s} run_id={run_id}")
    return len(files)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", default="local", choices=["local", "lyzr"])
    parser.add_argument("--payload-dir", default="./payloads")
    parser.add_argument("--fixtures", action="store_true",
                        help="Load the 5 canonical fixtures instead of the bulk dataset.")
    parser.add_argument("--no-init", action="store_true",
                        help="Append to existing DB instead of recreating.")
    args = parser.parse_args()

    if not args.no_init:
        init_db()
        print("Initialized fresh database: ehr_triage.db")

    validator = get_validator(args.engine)
    bulk_path = os.path.join(args.payload_dir, "encounters.jsonl")

    if args.fixtures or not os.path.exists(bulk_path):
        print(f"Loading canonical fixtures with engine '{validator.name}':\n")
        n = load_fixtures(validator, args.payload_dir)
        print(f"\nLoaded {n} fixture(s).")
    else:
        print(f"Loading bulk dataset with engine '{validator.name}'...")
        total, passed = load_bulk(validator, bulk_path)
        print(f"  processed {total} encounters: {passed} pass, {total - passed} fail "
              f"({round(100.0 * passed / total, 1)}% clean)")

    print("\nDone. Query with: sqlite3 ehr_triage.db < db/queries.sql")


if __name__ == "__main__":
    main()
"""
SQLite persistence for validation reports.
Parses the flat report schema into validation_runs + validation_issues.
"""

import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get("EHR_DB_PATH", "ehr_triage.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")


def init_db(db_path: str = DB_PATH):
    """Create tables from schema.sql. Drops and recreates."""
    with open(SCHEMA_PATH) as f:
        schema = f.read()
    conn = sqlite3.connect(db_path)
    conn.executescript(schema)
    conn.commit()
    conn.close()


def save_report(report: dict, model: str, source_system: str = None, db_path: str = DB_PATH) -> int:
    """Write one validation report. Returns the run_id."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    _insert_report(cur, report, model, source_system)
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id


def _insert_report(cur, report, model, source_system):
    cur.execute(
        "INSERT INTO validation_runs (payload_id, encounter_date, status, issue_count, model, source_system, run_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            report["payload_id"], report.get("encounter_date"),
            report["status"], report["issue_count"],
            model, source_system,
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )
    run_id = cur.lastrowid
    for issue in report["issues"]:
        cur.execute(
            "INSERT INTO validation_issues (run_id, field, problem, severity, remediation) "
            "VALUES (?, ?, ?, ?, ?)",
            (run_id, issue["field"], issue["problem"], issue["severity"], issue.get("remediation")),
        )
    return run_id


def save_reports_bulk(items, model: str, db_path: str = DB_PATH) -> int:
    """Write many reports on one connection. items = list of (report, source_system). Returns count."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    for report, source_system in items:
        _insert_report(cur, report, model, source_system)
    conn.commit()
    conn.close()
    return len(items)
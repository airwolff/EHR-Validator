"""
SQLite persistence for validation reports.
Uses SQLAlchemy Core so the same code works against SQLite locally
and Postgres on Render — only the DATABASE_URL env var changes.
"""

import json
import os
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine, text,
    MetaData, Table, Column,
    Integer, String, Text
)
from dotenv import load_dotenv

load_dotenv()

# SQLite locally, Postgres on Render.
# Local default keeps backward compatibility with existing dev workflow.
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(os.path.dirname(__file__), '..', 'ehr_triage.db')}"
)

# Render injects postgres:// but SQLAlchemy 2.x requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
metadata = MetaData()

validation_runs = Table(
    "validation_runs", metadata,
    Column("run_id",         Integer, primary_key=True, autoincrement=True),
    Column("payload_id",     String,  nullable=False),
    Column("encounter_date", String),
    Column("status",         String,  nullable=False),
    Column("issue_count",    Integer, nullable=False, default=0),
    Column("model",          String,  nullable=False),
    Column("source_system",  String),
    Column("run_at",         String,  nullable=False),
    # Phase 2 routing columns
    Column("routing_domain",  String),   # billing | clinical | identity | admin | clean
    Column("escalated",       Integer, default=0),  # 0 or 1
    Column("routing_reason",  Text),     # which field(s) triggered escalation
    Column("llm_summary",     Text),     # plain-English summary from LLM (escalated records only)
    Column("payload_json",    Text),     # raw record JSON, for the nightly agent batch
)

validation_issues = Table(
    "validation_issues", metadata,
    Column("issue_id",    Integer, primary_key=True, autoincrement=True),
    Column("run_id",      Integer, nullable=False),
    Column("field",       String,  nullable=False),
    Column("problem",     Text,    nullable=False),
    Column("severity",    String,  nullable=False),
    Column("remediation", Text),
)


def init_db():
    """Reset tables: DROP then CREATE. Destructive — wipes existing data.
    Use only for an explicit reset, not on every boot."""
    metadata.drop_all(engine)
    metadata.create_all(engine)


def ensure_tables():
    """Create any missing tables without dropping existing ones. Idempotent and
    safe to call on every boot — preserves data already in the DB."""
    metadata.create_all(engine)


def _insert_report(conn, report, model, source_system, routing=None, payload=None):
    """Insert one report. routing is an optional dict from the Phase 2 router.
    payload is the raw record; stored so the nightly agent batch can re-read the
    note/labs without the caller having to keep the original file around."""
    routing = routing or {}
    result = conn.execute(
        validation_runs.insert().values(
            payload_id=report["payload_id"],
            encounter_date=report.get("encounter_date"),
            status=report["status"],
            issue_count=report["issue_count"],
            model=model,
            source_system=source_system,
            run_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            routing_domain=routing.get("domain"),
            escalated=1 if routing.get("escalated") else 0,
            routing_reason=routing.get("reason"),
            llm_summary=routing.get("llm_summary"),
            payload_json=json.dumps(payload) if payload is not None else None,
        )
    )
    run_id = result.inserted_primary_key[0]
    for issue in report["issues"]:
        conn.execute(
            validation_issues.insert().values(
                run_id=run_id,
                field=issue["field"],
                problem=issue["problem"],
                severity=issue["severity"],
                remediation=issue.get("remediation"),
            )
        )
    return run_id


def save_report(report, model, source_system=None, routing=None, payload=None):
    """Write one report. Returns run_id."""
    with engine.begin() as conn:
        return _insert_report(conn, report, model, source_system, routing, payload)


def save_reports_bulk(items, model):
    """Write many reports in one transaction. Returns count.

    items = list of (report, source_system, routing, payload) tuples. routing and
    payload are optional per item, but dropping them here silently empties both the
    /stats domain breakdown and the nightly agent batch's source of records.
    """
    with engine.begin() as conn:
        for report, source_system, routing, payload in items:
            _insert_report(conn, report, model, source_system, routing, payload)
    return len(items)


def get_stats():
    """Return summary stats for the /stats endpoint."""
    with engine.connect() as conn:
        runs = conn.execute(text(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) AS passed "
            "FROM validation_runs"
        )).mappings().one()

        by_sev = {
            row["severity"]: row["n"]
            for row in conn.execute(text(
                "SELECT severity, COUNT(*) AS n "
                "FROM validation_issues GROUP BY severity"
            )).mappings()
        }

        by_domain = {
            row["routing_domain"]: row["n"]
            for row in conn.execute(text(
                "SELECT routing_domain, COUNT(*) AS n "
                "FROM validation_runs "
                "WHERE routing_domain IS NOT NULL "
                "GROUP BY routing_domain"
            )).mappings()
        }

    total = runs["total"] or 0
    return {
        "total_runs": total,
        "passed": runs["passed"] or 0,
        "pass_rate_pct": round(100.0 * (runs["passed"] or 0) / total, 1) if total else None,
        "issues_by_severity": by_sev,
        "records_by_domain": by_domain,
    }
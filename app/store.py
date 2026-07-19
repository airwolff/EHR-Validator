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
    # Stamped by the nightly agent batch once a record has been looked at — whether
    # or not it produced findings. A cleared record writes no findings, so absence of
    # findings cannot mean "not yet processed"; without this the batch would re-run
    # every clean record (and re-spend credits) forever.
    Column("agent_processed_at", String),
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

# Findings from the LLM agents live HERE, never in validation_issues. Keeping the two
# engines' output in separate tables is the presentation argument: at demo time we can
# show exactly which defects the deterministic rules caught and which only the agents did.
agent_findings = Table(
    "agent_findings", metadata,
    Column("finding_id",   Integer, primary_key=True, autoincrement=True),
    Column("run_id",       Integer, nullable=False),
    Column("batch_date",   String,  nullable=False),
    Column("created_at",   String,  nullable=False),
    Column("domain",       String,  nullable=False),
    Column("field",        String,  nullable=False),
    Column("problem",      Text,    nullable=False),
    Column("severity",     String,  nullable=False),
    Column("adjudication", String),
    Column("evidence",     Text),
    Column("confidence",   String),
    Column("remediation",  Text),
    Column("owner",        String),
)

# Task 13: the rules-vs-LLM experiment. One row per try in comparison_runs; one row per
# grade in comparison_results. Kept separate from validation_issues / agent_findings for
# the same reason those two are separate: at demo time each engine's output is its own
# table, and the comparison is a JOIN, not an untangling.
comparison_runs = Table(
    "comparison_runs", metadata,
    Column("comparison_run_id", Integer, primary_key=True, autoincrement=True),
    Column("run_number",       Integer, nullable=False),   # try 1..5
    Column("mode",             String,  nullable=False),   # live | replay
    Column("ran_at",           String,  nullable=False),
    Column("permutation",      Text,    nullable=False),   # record ids, comma-joined, order sent
    Column("usable",           Integer, nullable=False, default=1),  # 0 = reply unreadable
    # Findings too malformed to grade (bad severity, unknown record id). Counted, never
    # silently discarded — same rule as the batch's dropped findings.
    Column("dropped_findings", Integer, nullable=False, default=0),
)

comparison_results = Table(
    "comparison_results", metadata,
    Column("result_id",         Integer, primary_key=True, autoincrement=True),
    Column("comparison_run_id", Integer, nullable=False),
    Column("record_id",         String,  nullable=False),
    Column("field",             String,  nullable=False),
    Column("rule_severity",     String),  # NULL on false_alarm — the rules said nothing here
    Column("llm_severity",      String),  # NULL on missed — the AI said nothing here
    Column("outcome",           String,  nullable=False),
    # outcome: caught | severity_mismatch | missed | false_alarm
)

# The month-end auditor's demographic lens. Filled by the loader, queried by Q12 and
# get_audit_aggregates. A separate table (not JSON functions over payload_json) so the
# missingness-by-demographic COUNT is honestly SQL's catch, not Python's.
record_demographics = Table(
    "record_demographics", metadata,
    Column("payload_id",    String, primary_key=True),
    Column("age",           Integer),
    Column("sex",           String),
    Column("race",          String),
    Column("zip",           String),
    Column("source_system", String),
)

# Worklist precedence. Deliberately separate from router.DOMAIN_PRIORITY: that one picks
# a record's primary domain, this one sorts a human's queue.
# Every domain router.py can emit must appear here. A domain missing from this map sorts
# silently to the bottom of the worklist, which is how the labs defects ended up misfiled
# under `admin` in Task 3 — the skew is invisible until someone reads the analytics.
# ("clean" is deliberately absent: a *finding* is never clean. It falls to UNRANKED.)
WORKLIST_DOMAIN_ORDER = {"identity": 0, "clinical": 1, "billing": 2, "admin": 3}
WORKLIST_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
UNRANKED = 9  # unrecognised domain/severity: sorts last rather than crashing the worklist


def _utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
            run_at=_utc_now(),
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


def demographics_from_payload(payload_id, payload):
    """The demographic slice the auditor and Q12 see. Pure; missing fields are None,
    because 'missing' is precisely the signal the missingness queries count."""
    patient = (payload or {}).get("patient") or {}
    metadata = (payload or {}).get("metadata") or {}
    return {
        "payload_id": payload_id,
        "age": patient.get("age"),
        "sex": patient.get("sex"),
        "race": patient.get("race"),
        "zip": patient.get("zip"),
        "source_system": metadata.get("source_system"),
    }


def save_demographics(rows):
    """Write demographic rows. Delete-then-insert per payload_id in one transaction,
    so a re-load replaces rather than duplicates — same manners as save_comparison_run."""
    with engine.begin() as conn:
        for r in rows:
            conn.execute(record_demographics.delete().where(
                record_demographics.c.payload_id == r["payload_id"]))
            conn.execute(record_demographics.insert().values(**r))
    return len(rows)


def record_agent_result(run_id, findings, batch_date):
    """Record what the agent batch made of one record: write its findings AND stamp it
    processed, in ONE transaction. Returns the number of findings written.

    This is the only way to write agent findings, on purpose. Writing the findings and
    stamping the marker as two separate calls has two silent failure modes: die between
    them and the record is re-read next run and its findings written a second time (the
    worklist double-counts), or stamp first and fail the write and the record leaves the
    inbox forever with its defects unreported. One transaction, so neither is reachable.

    Pass findings=[] for a record the agents CLEARED — it still gets stamped, so we don't
    re-read (and re-pay for) a clean record on every future run.
    """
    now = _utc_now()
    with engine.begin() as conn:
        for f in findings:
            conn.execute(
                agent_findings.insert().values(
                    run_id=run_id,
                    batch_date=batch_date,
                    created_at=now,
                    domain=f["domain"],
                    field=f["field"],
                    problem=f["problem"],
                    severity=f["severity"],
                    adjudication=f.get("adjudication"),
                    evidence=f.get("evidence"),
                    confidence=f.get("confidence"),
                    remediation=f.get("remediation"),
                    owner=f.get("owner"),
                )
            )
        stamped = conn.execute(
            validation_runs.update()
            .where(validation_runs.c.run_id == run_id)
            .values(agent_processed_at=now)
        ).rowcount
    if stamped == 0:
        raise ValueError(
            f"run_id {run_id} does not exist — findings would be orphaned and the record "
            f"never marked processed"
        )
    return len(findings)


def save_comparison_run(run_number, mode, permutation, usable, results, dropped_findings=0):
    """Save one graded try of the rules-vs-LLM experiment. Returns comparison_run_id.

    Delete-then-insert in ONE transaction: re-grading the same try (same run_number and
    mode) REPLACES its old rows. Recordings are the experiment's source of truth, so a
    re-grade is routine — but if each re-grade appended rows, 'missed in X of N runs'
    would quietly count the same try twice. A live try and a replay re-grade are
    deliberately different identities (mode is part of the key).
    """
    now = _utc_now()
    with engine.begin() as conn:
        old = conn.execute(
            comparison_runs.select().where(
                (comparison_runs.c.run_number == run_number)
                & (comparison_runs.c.mode == mode))
        ).mappings().all()
        old_ids = [r["comparison_run_id"] for r in old]
        if old_ids:
            conn.execute(comparison_results.delete().where(
                comparison_results.c.comparison_run_id.in_(old_ids)))
            conn.execute(comparison_runs.delete().where(
                comparison_runs.c.comparison_run_id.in_(old_ids)))
        cid = conn.execute(
            comparison_runs.insert().values(
                run_number=run_number,
                mode=mode,
                ran_at=now,
                permutation=",".join(permutation),
                usable=1 if usable else 0,
                dropped_findings=dropped_findings,
            )
        ).inserted_primary_key[0]
        for r in results:
            conn.execute(
                comparison_results.insert().values(
                    comparison_run_id=cid,
                    record_id=r["record_id"],
                    field=r["field"],
                    rule_severity=r.get("rule_severity"),
                    llm_severity=r.get("llm_severity"),
                    outcome=r["outcome"],
                )
            )
    return cid


def get_noted_records():
    """The nightly agent batch's inbox: records carrying a clinical note that the batch
    has not processed yet. Returns [{"run_id": int, "payload": dict}].

    Selection is on NOTE PRESENCE, not on escalated/critical — a record the rules find
    nothing wrong with must still reach the agents. That zero-rule-issue record is the
    catch the whole demo turns on."""
    out = []
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT run_id, payload_json FROM validation_runs "
            "WHERE payload_json IS NOT NULL AND agent_processed_at IS NULL "
            "ORDER BY run_id"
        )).mappings()
        for row in rows:
            payload = json.loads(row["payload_json"])
            # A payload that isn't a JSON object has no note and no fields to adjudicate.
            # Skip it rather than let one malformed row take down the whole batch.
            if not isinstance(payload, dict):
                continue
            if (payload.get("clinical_note") or "").strip():
                out.append({"run_id": row["run_id"], "payload": payload})
    return out


def get_worklist(batch_date):
    """Findings for one batch, sorted domain-precedence then severity.
    ORDER BY finding_id gives ties a defined order (insertion order) — without it SQLite
    is free to return tied findings in any order and the human worklist reshuffles between
    identical runs."""
    with engine.connect() as conn:
        rows = [dict(r) for r in conn.execute(text(
            "SELECT * FROM agent_findings WHERE batch_date = :d ORDER BY finding_id"),
            {"d": batch_date}
        ).mappings()]
    rows.sort(key=lambda f: (WORKLIST_DOMAIN_ORDER.get(f["domain"], UNRANKED),
                             WORKLIST_SEVERITY_ORDER.get(f["severity"], UNRANKED)))
    return rows


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
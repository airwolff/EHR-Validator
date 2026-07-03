"""
FastAPI backend for the EHR triage pipeline.

Endpoints:
  POST /validate   — accept one encounter payload, validate, persist, return report
  GET  /stats      — return current data-quality summary from SQL
  GET  /health     — liveness check

Run locally:
  uvicorn app.main:app --reload
Then POST a payload, e.g.:
  curl -X POST localhost:8000/validate -H "Content-Type: application/json" \
       --data @payloads/payload_bad_values.json
"""

import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.validator import get_validator
from app.store import init_db, save_report, DB_PATH

ENGINE = os.environ.get("EHR_ENGINE", "local")  # 'local' or 'lyzr'


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if the DB doesn't exist yet. Does not wipe an existing DB.
    if not os.path.exists(DB_PATH):
        init_db()
    yield


app = FastAPI(title="EHR Data Quality Triage", version="1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "engine": ENGINE}


@app.post("/validate")
def validate(payload: dict):
    validator = get_validator(ENGINE)
    report = validator.validate(payload)
    source = payload.get("metadata", {}).get("source_system")
    run_id = save_report(report, model=validator.name, source_system=source)
    report["run_id"] = run_id
    return JSONResponse(report)


@app.get("/stats")
def stats():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN status='pass' THEN 1 ELSE 0 END) AS passed "
        "FROM validation_runs"
    )
    runs = dict(cur.fetchone())
    cur.execute(
        "SELECT severity, COUNT(*) AS n FROM validation_issues GROUP BY severity"
    )
    by_sev = {row["severity"]: row["n"] for row in cur.fetchall()}
    conn.close()
    total = runs["total"] or 0
    return {
        "total_runs": total,
        "passed": runs["passed"] or 0,
        "pass_rate_pct": round(100.0 * (runs["passed"] or 0) / total, 1) if total else None,
        "issues_by_severity": by_sev,
    }

"""
FastAPI backend for the EHR triage pipeline.

Endpoints:
  POST /validate   — accept one encounter payload, validate, route, persist, return report
  GET  /stats      — return current data-quality summary from SQL
  GET  /health     — liveness check

Run locally:
  uvicorn app.main:app --reload
Then POST a payload, e.g.:
  curl -X POST localhost:8000/validate -H "Content-Type: application/json" \
       --data @payloads/payload_bad_values.json
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.validator import get_validator
from app.router import route
from app.store import ensure_tables, save_report, get_stats

ENGINE = os.environ.get("EHR_ENGINE", "local")  # 'local' or 'lyzr'


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist yet. Non-destructive: never wipes data.
    ensure_tables()
    yield


app = FastAPI(title="EHR Data Quality Triage", version="1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "engine": ENGINE}


@app.post("/validate")
def validate(payload: dict):
    validator = get_validator(ENGINE)
    report = validator.validate(payload)

    # Phase 2: decide owning domain + escalation, then persist alongside the report.
    routing = route(report)
    source = payload.get("metadata", {}).get("source_system")
    run_id = save_report(
        report, model=validator.name, source_system=source, routing=routing
    )

    report["run_id"] = run_id
    report["routing"] = routing
    return JSONResponse(report)


@app.get("/stats")
def stats():
    return get_stats()

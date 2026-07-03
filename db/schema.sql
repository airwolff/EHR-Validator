-- EHR Data Quality Triage — relational schema
-- Engine: SQLite (zero-install demo). Portable to Postgres with the noted swaps.
--
-- One validation run per payload processed. Each run has zero or more issues.
-- This models the agent's flat JSON output into a queryable relational store
-- so data-quality trends can be analyzed with SQL.

DROP TABLE IF EXISTS validation_issues;
DROP TABLE IF EXISTS validation_runs;

CREATE TABLE validation_runs (
    run_id         INTEGER PRIMARY KEY AUTOINCREMENT,  -- Postgres: GENERATED ALWAYS AS IDENTITY
    payload_id     TEXT    NOT NULL,
    encounter_date TEXT,                                -- clinical date from the record (for trend analysis)
    status         TEXT    NOT NULL CHECK (status IN ('pass', 'fail')),
    issue_count    INTEGER NOT NULL DEFAULT 0,
    model          TEXT    NOT NULL,                    -- which validation engine produced this
    source_system  TEXT,                                -- e.g. Epic, Cerner — from payload metadata
    run_at         TEXT    NOT NULL                     -- ISO 8601 UTC load time; Postgres: TIMESTAMPTZ
);

CREATE TABLE validation_issues (
    issue_id    INTEGER PRIMARY KEY AUTOINCREMENT,     -- Postgres: GENERATED ALWAYS AS IDENTITY
    run_id      INTEGER NOT NULL REFERENCES validation_runs(run_id) ON DELETE CASCADE,
    field       TEXT    NOT NULL,
    problem     TEXT    NOT NULL,
    severity    TEXT    NOT NULL CHECK (severity IN ('critical', 'warning', 'info')),
    remediation TEXT
);

-- Indexes for the analytics queries in queries.sql
CREATE INDEX idx_issues_run      ON validation_issues(run_id);
CREATE INDEX idx_issues_severity ON validation_issues(severity);
CREATE INDEX idx_issues_field    ON validation_issues(field);
CREATE INDEX idx_runs_source     ON validation_runs(source_system);
CREATE INDEX idx_runs_at         ON validation_runs(run_at);
CREATE INDEX idx_runs_enc_date   ON validation_runs(encounter_date);
-- EHR Data Quality Triage — analytics queries
-- These are the questions a healthcare data-quality analyst actually asks.
-- Each is self-contained. Run individually or as a suite.

-- ---------------------------------------------------------------------------
-- Q1. Overall pass rate.
-- What fraction of processed records were clean?
-- ---------------------------------------------------------------------------
SELECT
    COUNT(*)                                               AS total_runs,
    SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END)       AS passed,
    SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END)       AS failed,
    ROUND(100.0 * SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) / COUNT(*), 1)
                                                           AS pass_rate_pct
FROM validation_runs;

-- ---------------------------------------------------------------------------
-- Q2. Issue volume by severity.
-- Where is the triage load concentrated?
-- ---------------------------------------------------------------------------
SELECT
    severity,
    COUNT(*)                                               AS issue_count,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM validation_issues), 1)
                                                           AS pct_of_all_issues
FROM validation_issues
GROUP BY severity
ORDER BY
    CASE severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END;

-- ---------------------------------------------------------------------------
-- Q3. Top failing fields, ranked.
-- Which fields break most often? Window function to rank.
-- ---------------------------------------------------------------------------
SELECT
    field,
    COUNT(*)                                               AS failure_count,
    RANK() OVER (ORDER BY COUNT(*) DESC)                   AS failure_rank
FROM validation_issues
GROUP BY field
ORDER BY failure_count DESC
LIMIT 10;

-- ---------------------------------------------------------------------------
-- Q4. Error profile by source system.
-- Which upstream EHR feeds send the dirtiest data?
-- ---------------------------------------------------------------------------
SELECT
    r.source_system,
    COUNT(DISTINCT r.run_id)                               AS records_processed,
    COUNT(i.issue_id)                                      AS total_issues,
    SUM(CASE WHEN i.severity = 'critical' THEN 1 ELSE 0 END) AS critical_issues,
    ROUND(1.0 * COUNT(i.issue_id) / COUNT(DISTINCT r.run_id), 2)
                                                           AS avg_issues_per_record
FROM validation_runs r
LEFT JOIN validation_issues i ON i.run_id = r.run_id
GROUP BY r.source_system
ORDER BY total_issues DESC;

-- ---------------------------------------------------------------------------
-- Q5. Most common specific problems.
-- The actual defect text, grouped — drives remediation priorities.
-- ---------------------------------------------------------------------------
SELECT
    severity,
    problem,
    COUNT(*)                                               AS occurrences
FROM validation_issues
GROUP BY severity, problem
ORDER BY occurrences DESC, severity
LIMIT 15;

-- ---------------------------------------------------------------------------
-- Q6. Critical-only worklist.
-- The records a human must touch before processing — joins issues back to runs.
-- ---------------------------------------------------------------------------
SELECT
    r.payload_id,
    r.source_system,
    i.field,
    i.problem,
    i.remediation
FROM validation_issues i
JOIN validation_runs r ON r.run_id = i.run_id
WHERE i.severity = 'critical'
ORDER BY r.payload_id, i.field;

-- ---------------------------------------------------------------------------
-- Q7. Daily clean rate by clinical encounter date (trend).
-- Groups on the date care was delivered, not when the row was loaded.
-- ---------------------------------------------------------------------------
SELECT
    encounter_date,
    COUNT(*)                                               AS records,
    SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END)       AS clean,
    ROUND(100.0 * SUM(CASE WHEN status = 'pass' THEN 1 ELSE 0 END) / COUNT(*), 1)
                                                           AS clean_rate_pct
FROM validation_runs
WHERE encounter_date LIKE '____-__-__'
GROUP BY encounter_date
ORDER BY encounter_date;
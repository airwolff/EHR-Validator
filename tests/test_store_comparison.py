"""The comparison experiment's storage: one row per try, one row per grade,
and re-saving a try REPLACES its old rows instead of duplicating them."""
from sqlalchemy import text


def _count(store, table):
    with store.engine.connect() as conn:
        return conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def test_comparison_run_and_results_are_written(fresh_store):
    rows = [
        {"record_id": "payload_bad_values", "field": "vitals.spo2_pct",
         "rule_severity": "critical", "llm_severity": None, "outcome": "missed"},
        {"record_id": "payload_clean", "field": "vitals.temp_f",
         "rule_severity": None, "llm_severity": "warning", "outcome": "false_alarm"},
    ]
    cid = fresh_store.save_comparison_run(
        1, "replay", ["payload_clean", "payload_bad_values"],
        usable=True, results=rows, dropped_findings=2)

    with fresh_store.engine.connect() as conn:
        run = conn.execute(text("SELECT * FROM comparison_runs")).mappings().one()
        res = conn.execute(text(
            "SELECT * FROM comparison_results ORDER BY result_id")).mappings().all()

    assert run["comparison_run_id"] == cid
    assert run["run_number"] == 1
    assert run["mode"] == "replay"
    assert run["usable"] == 1
    assert run["dropped_findings"] == 2
    assert run["permutation"] == "payload_clean,payload_bad_values"
    assert run["ran_at"]  # stamped
    assert len(res) == 2
    assert res[0]["outcome"] == "missed" and res[0]["llm_severity"] is None
    assert res[1]["outcome"] == "false_alarm" and res[1]["rule_severity"] is None
    assert all(r["comparison_run_id"] == cid for r in res)


def test_resaving_same_try_replaces_not_duplicates(fresh_store):
    row = [{"record_id": "payload_clean", "field": "x",
            "rule_severity": "info", "llm_severity": "info", "outcome": "caught"}]
    fresh_store.save_comparison_run(1, "replay", ["a"], usable=True, results=row)
    fresh_store.save_comparison_run(1, "replay", ["a"], usable=False, results=[])

    assert _count(fresh_store, "comparison_runs") == 1
    assert _count(fresh_store, "comparison_results") == 0  # old grades gone too
    with fresh_store.engine.connect() as conn:
        run = conn.execute(text("SELECT * FROM comparison_runs")).mappings().one()
    assert run["usable"] == 0


def test_same_run_number_different_mode_coexist(fresh_store):
    """A live try and its replay re-grade are different rows on purpose —
    mode is part of the identity."""
    fresh_store.save_comparison_run(1, "live", ["a"], usable=True, results=[])
    fresh_store.save_comparison_run(1, "replay", ["a"], usable=True, results=[])
    assert _count(fresh_store, "comparison_runs") == 2

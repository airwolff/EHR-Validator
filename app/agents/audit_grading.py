"""Grade a month-end audit against the planted answer key.

Deliberately dumb: case-insensitive whole-word term counting over each pattern's
name + hypothesis + recommended_action. caught >= 2 distinct terms, partial == 1,
missed == 0. Dumb is the point — a grader anyone can re-run by eye is a grader
nobody argues with on stage. Same delete-then-insert manners as every other grade
table (store.save_audit_report already cascades old grades away)."""
import json
import os
import re

from app import store

ANSWER_KEY_PATH = os.path.join(os.path.dirname(__file__), "..", "..",
                               "scripts", "audit_answer_key.json")


def _term_hits(text, terms):
    lowered = text.lower()
    return sum(1 for t in terms
               if re.search(r"(?<!\w)" + re.escape(t.lower()) + r"(?!\w)", lowered))


def grade_patterns(kept, answer_key):
    """Pure grading. Each planted key is matched to its best-scoring kept pattern."""
    texts = [" ".join([p["name"], p["hypothesis"], p["recommended_action"]])
             for p in kept]
    grades = []
    for planted in answer_key["planted"]:
        scores = [_term_hits(t, planted["terms"]) for t in texts]
        best = max(scores) if scores else 0
        outcome = "caught" if best >= 2 else ("partial" if best == 1 else "missed")
        grades.append({"planted_key": planted["key"], "outcome": outcome,
                       "matched_index": scores.index(best) if best else None})
    return grades


def grade_persisted_report(month, mode):
    """Read the persisted report for (month, mode), grade it, write audit_grades."""
    from sqlalchemy import text as sql
    with open(os.path.normpath(ANSWER_KEY_PATH)) as f:
        answer_key = json.load(f)
    with store.engine.connect() as conn:
        report = conn.execute(sql(
            "SELECT report_id FROM audit_reports "
            "WHERE report_month = :m AND mode = :o"),
            {"m": month, "o": mode}).mappings().one_or_none()
        if report is None:
            raise ValueError(f"No persisted audit for {month} ({mode}) — run the audit first.")
        rows = conn.execute(sql(
            "SELECT pattern_id, name, hypothesis, recommended_action "
            "FROM audit_patterns WHERE report_id = :r ORDER BY pattern_id"),
            {"r": report["report_id"]}).mappings().all()
    kept = [{"name": r["name"], "hypothesis": r["hypothesis"],
             "recommended_action": r["recommended_action"]} for r in rows]
    grades = grade_patterns(kept, answer_key)
    matched = {g["matched_index"] for g in grades
               if g["matched_index"] is not None and g["outcome"] == "caught"}
    invented = len(kept) - len(matched & set(range(len(kept)))) if kept else 0
    with store.engine.begin() as conn:
        conn.execute(store.audit_grades.delete().where(
            store.audit_grades.c.report_id == report["report_id"]))
        for g in grades:
            pattern_id = rows[g["matched_index"]]["pattern_id"] if g["matched_index"] is not None else None
            conn.execute(store.audit_grades.insert().values(
                report_id=report["report_id"], planted_key=g["planted_key"],
                outcome=g["outcome"], matched_pattern_id=pattern_id))
    return {"grades": grades, "invented": invented}

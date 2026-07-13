"""
Phase 2 routing logic.

The router inspects a validated report and decides:
  1. Which domain owns the problem (billing, clinical, identity, admin)
  2. Whether it should escalate to the LLM for secondary analysis
  3. A plain-English reason for the routing decision

Rules:
  - A record can only have ONE primary routing domain (highest-priority domain wins)
  - Escalation triggers on any critical issue in the record
  - Clean records (status=pass) get domain=clean, escalated=False

Domain priority order (when multiple domains have failures):
  identity > billing > clinical > admin

Field → domain mapping:
  billing:  facility_npi, provider_npi, procedures[*].code, procedures[*].code_system
  clinical: vitals.*, diagnoses[*].code, diagnoses[*].code_system, labs[*].*
  identity: patient.patient_id, patient.dob, patient.sex, patient.age
  admin:    encounter.encounter_id, encounter.encounter_date,
            metadata.extract_timestamp, metadata.source_system
"""

DOMAIN_PRIORITY = ["identity", "billing", "clinical", "admin"]

FIELD_DOMAIN = {
    # identity
    "patient.patient_id": "identity",
    "patient.dob":        "identity",
    "patient.sex":        "identity",
    "patient.age":        "identity",
    # billing
    "encounter.facility_npi": "billing",
    "encounter.provider_npi": "billing",
    # clinical
    "vitals.systolic_bp":   "clinical",
    "vitals.diastolic_bp":  "clinical",
    "vitals.heart_rate_bpm":"clinical",
    "vitals.temp_f":        "clinical",
    "vitals.spo2_pct":      "clinical",
}


def _field_to_domain(field: str) -> str:
    """Map a field path to its owning domain."""
    # exact match first
    if field in FIELD_DOMAIN:
        return FIELD_DOMAIN[field]
    # prefix matches for array fields
    if field.startswith("procedures["):
        return "billing"
    if field.startswith("diagnoses["):
        return "clinical"
    if field.startswith("labs["):
        return "clinical"
    if field.startswith("vitals."):
        return "clinical"
    if field.startswith("patient."):
        return "identity"
    if field.startswith("encounter."):
        return "admin"
    if field.startswith("metadata."):
        return "admin"
    return "admin"  # safe default


def route(report: dict) -> dict:
    """
    Inspect a validated report and return a routing decision dict:
      {
        domain:    str,   # primary owning domain
        escalated: bool,  # True if any critical issue present
        reason:    str,   # human-readable explanation
      }
    """
    if report["status"] == "pass":
        return {"domain": "clean", "escalated": False, "reason": "No issues found."}

    issues = report["issues"]

    # collect domains touched by this record's issues
    domains_hit = set()
    critical_fields = []
    for issue in issues:
        d = _field_to_domain(issue["field"])
        domains_hit.add(d)
        if issue["severity"] == "critical":
            critical_fields.append(issue["field"])

    # pick highest-priority domain
    primary_domain = "admin"
    for d in DOMAIN_PRIORITY:
        if d in domains_hit:
            primary_domain = d
            break

    escalated = len(critical_fields) > 0

    if escalated:
        reason = (
            f"Routed to {primary_domain}. "
            f"Critical issue(s) on: {', '.join(critical_fields)}. "
            f"Escalated for LLM review."
        )
    else:
        reason = (
            f"Routed to {primary_domain}. "
            f"Warning/info issues only — no escalation required."
        )

    return {
        "domain":    primary_domain,
        "escalated": escalated,
        "reason":    reason,
    }
"""
Validation engines for the EHR triage pipeline.

LocalValidator   — deterministic reference implementation of the prompt rules.
                   Runs with no external dependencies or credits. This is also
                   the parallel implementation kept outside program infrastructure.
LyzrValidator     — calls the deployed Lyzr agent API. Stubbed until you paste in
                   your endpoint and key. Same output contract as LocalValidator.

Both return the flat report schema:
  {payload_id, status, issue_count, issues:[{field, problem, severity, remediation}]}
"""

import os
import re

# Load a local .env file if present (values like LYZR_API_KEY, LYZR_AGENT_ID).
# Falls back silently if python-dotenv is not installed.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- format patterns ---------------------------------------------------------
ICD10 = re.compile(r"^[A-Z][0-9]{2}(\.[A-Z0-9]{1,4})?$")
CPT = re.compile(r"^[0-9]{5}$")
NPI = re.compile(r"^[0-9]{10}$")
DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
TIMESTAMP = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")

REQUIRED = [
    ("encounter", "encounter_id"),
    ("encounter", "encounter_date"),
    ("encounter", "facility_npi"),
    ("encounter", "provider_npi"),
    ("patient", "patient_id"),
    ("patient", "dob"),
    # patient.sex is deliberately NOT required — declining to state sex is a
    # legitimate answer, not a data defect. See SEX_UNDECLARED below.
]

# vital: (pass_lo, pass_hi, warn_lo, warn_hi)
# outside [warn_lo, warn_hi] => critical; inside warn band but outside pass => warning
VITALS = {
    "age": (0, 120, 0, 120),
    "systolic_bp": (70, 200, 50, 300),
    "diastolic_bp": (40, 120, 30, 150),
    "heart_rate_bpm": (30, 200, 20, 300),
    "temp_f": (95, 104, 93, 107),
    "spo2_pct": (90, 100, 70, 100),
}


# Minimal hand-picked sex-restricted ICD-10 prefixes. Detection is deterministic;
# the agent only adjudicates which field (sex vs code) is the real error.
SEX_RESTRICTED_CODES = {
    "female_only": ("O", "Z34", "Z33", "N80", "C53"),   # pregnancy, cervix, endometriosis
    "male_only":   ("N40", "C61", "N41"),               # BPH, prostate
}

# Spellings that resolve to a definite sex, per FHIR AdministrativeGender.
SEX_SYNONYMS = {
    "M": "M", "MALE": "M",
    "F": "F", "FEMALE": "F",
}

# Answers that decline to state a sex. These are VALID values, not defects: a
# patient may always opt out, and the pipeline must never penalise that. They
# produce no issue at any severity, and they suppress the sex-restricted-code
# rule below — with no asserted sex there is nothing for a code to contradict.
SEX_UNDECLARED = {
    "", "U", "UN", "UNK", "UNKNOWN", "O", "OTHER", "X", "ASKU",
    "DECLINED", "DECLINED TO STATE", "PREFER NOT TO SAY", "NOT RECORDED",
}


def _normalise_sex(raw):
    """Resolve a raw sex value to 'M', 'F', None (undeclared), or the cleaned
    string itself when it maps to nothing we recognise."""
    if raw is None:
        return None
    cleaned = str(raw).strip().upper()
    if cleaned in SEX_UNDECLARED:
        return None
    return SEX_SYNONYMS.get(cleaned, cleaned)


def _issue(field, problem, severity, remediation):
    return {"field": field, "problem": problem, "severity": severity, "remediation": remediation}


def _classify_vital(name, value):
    pass_lo, pass_hi, warn_lo, warn_hi = VITALS[name]
    if name == "heart_rate_bpm" and value == 0:
        return _issue(f"vitals.{name}", "Heart rate of 0 is not a valid vital for a live encounter.",
                      "critical", "Re-capture heart rate; 0 indicates a missing or failed reading.")
    if value < warn_lo or value > warn_hi:
        return _issue(f"vitals.{name}", f"Value {value} is outside the plausible range; near-certain data error.",
                      "critical", f"Verify and correct {name}; plausible band is {warn_lo}-{warn_hi}.")
    if value < pass_lo or value > pass_hi:
        return _issue(f"vitals.{name}", f"Value {value} is possible but implausible for a routine encounter.",
                      "warning", f"Confirm {name} with source; expected {pass_lo}-{pass_hi}.")
    return None


class LocalValidator:
    name = "local-reference-v1"

    def validate(self, payload: dict) -> dict:
        issues = []
        enc = payload.get("encounter", {})
        pat = payload.get("patient", {})
        vit = payload.get("vitals", {})

        # 1. required fields
        for section, key in REQUIRED:
            val = payload.get(section, {}).get(key)
            if val in (None, ""):
                issues.append(_issue(f"{section}.{key}", "Required field is missing or empty.",
                                     "critical", f"Populate {section}.{key}."))

        # 2. date formats
        if enc.get("encounter_date") and not DATE.match(str(enc["encounter_date"])):
            issues.append(_issue("encounter.encounter_date",
                                 f"Date '{enc['encounter_date']}' is not YYYY-MM-DD.",
                                 "warning", "Reformat to ISO 8601 date YYYY-MM-DD."))
        if pat.get("dob") and not DATE.match(str(pat["dob"])):
            issues.append(_issue("patient.dob", f"Date '{pat['dob']}' is not YYYY-MM-DD.",
                                 "warning", "Reformat to ISO 8601 date YYYY-MM-DD."))
        ts = payload.get("metadata", {}).get("extract_timestamp")
        if ts and not TIMESTAMP.match(str(ts)):
            issues.append(_issue("metadata.extract_timestamp",
                                 f"Timestamp '{ts}' is not YYYY-MM-DDThh:mm:ssZ.",
                                 "warning", "Reformat to ISO 8601 timestamp with T separator and Z suffix."))

        # 3. NPI
        for key in ("facility_npi", "provider_npi"):
            v = enc.get(key)
            if v and not NPI.match(str(v)):
                issues.append(_issue(f"encounter.{key}", f"NPI '{v}' is not exactly 10 digits.",
                                     "critical", "Correct to a valid 10-digit NPI."))

        # 4. vitals (age lives under patient; the rest under vitals)
        if isinstance(pat.get("age"), (int, float)):
            found = _classify_vital("age", pat["age"])
            if found:
                found["field"] = "patient.age"
                issues.append(found)
        for name in VITALS:
            if name == "age":
                continue
            if name in vit and isinstance(vit[name], (int, float)):
                found = _classify_vital(name, vit[name])
                if found:
                    issues.append(found)

        # 5. codes
        for idx, dx in enumerate(payload.get("diagnoses", [])):
            code = dx.get("code", "")
            if not ICD10.match(str(code)):
                issues.append(_issue(f"diagnoses[{idx}].code",
                                     f"ICD-10 code '{code}' is malformed.",
                                     "critical", "Correct to valid ICD-10-CM format (e.g. J06.9)."))
            if dx.get("code_system") not in ("ICD-10-CM", None):
                issues.append(_issue(f"diagnoses[{idx}].code_system",
                                     f"code_system '{dx.get('code_system')}' is not exact 'ICD-10-CM'.",
                                     "info", "Set code_system to exact uppercase 'ICD-10-CM'."))
        for idx, pr in enumerate(payload.get("procedures", [])):
            code = pr.get("code", "")
            if not CPT.match(str(code)):
                issues.append(_issue(f"procedures[{idx}].code",
                                     f"CPT code '{code}' is malformed; must be exactly 5 digits.",
                                     "critical", "Correct to a valid 5-digit CPT code."))
            if pr.get("code_system") not in ("CPT", None):
                issues.append(_issue(f"procedures[{idx}].code_system",
                                     f"code_system '{pr.get('code_system')}' is not exact 'CPT'.",
                                     "info", "Set code_system to exact uppercase 'CPT'."))

        # 6. sex-restricted diagnosis codes (deterministic detection)
        #
        # Fires ONLY on a definitely-stated M or F. An undeclared sex ("prefer not
        # to say", unknown, other, absent) yields sex=None and the rule stays
        # silent: there is no asserted sex for the code to contradict, so there is
        # no defect. Opting out must never cost the patient an issue.
        sex = _normalise_sex(pat.get("sex"))

        if sex is not None and sex not in ("M", "F"):
            # A value we can't map. This is an encoding defect in the source
            # system, not a problem with the patient — hence info, and the
            # remediation points at the integration.
            issues.append(_issue("patient.sex",
                f"Sex '{pat.get('sex')}' is not a recognised FHIR AdministrativeGender value.",
                "info", "Map the source value to male/female/other/unknown at ingest."))
        elif sex in ("M", "F"):
            restricted = "female_only" if sex == "M" else "male_only"
            other_sex = "female" if sex == "M" else "male"
            for dx in payload.get("diagnoses", []):
                code = str(dx.get("code", "")).strip().upper()
                if code.startswith(SEX_RESTRICTED_CODES[restricted]):
                    issues.append(_issue("patient.sex",
                        f"Diagnosis {code} is {other_sex}-restricted but patient.sex is '{sex}'.",
                        "critical", "Reconcile patient sex vs diagnosis; one is a data error."))
                    break   # one contradiction per record; don't repeat the same defect

        return {
            "payload_id": enc.get("encounter_id") or "UNKNOWN",
            "encounter_date": enc.get("encounter_date"),
            "status": "fail" if issues else "pass",
            "issue_count": len(issues),
            "issues": issues,
        }


class LyzrValidator:
    """Calls the deployed Lyzr agent via the v3 inference chat API.

    Configure via environment variables before use:
      LYZR_API_KEY   - the x-api-key value from the Deploy tab
      LYZR_AGENT_ID  - the agent_id from the Deploy tab
      LYZR_USER_ID   - your Lyzr account email
      LYZR_AGENT_URL - optional; defaults to the standard v3 endpoint
    """
    name = "lyzr-agent"
    DEFAULT_URL = "https://agent-prod.studio.lyzr.ai/v3/inference/chat/"

    def __init__(self):
        self.endpoint = os.environ.get("LYZR_AGENT_URL", self.DEFAULT_URL)
        self.api_key = os.environ.get("LYZR_API_KEY")
        self.agent_id = os.environ.get("LYZR_AGENT_ID")
        self.user_id = os.environ.get("LYZR_USER_ID", "default_user")

    def validate(self, payload: dict) -> dict:
        if not self.api_key or not self.agent_id:
            raise RuntimeError(
                "LyzrValidator not configured. Set LYZR_API_KEY and LYZR_AGENT_ID "
                "(and optionally LYZR_USER_ID) from the agent's Deploy tab. "
                "Until then use the local validator."
            )
        import json
        import uuid
        import urllib.request

        body = json.dumps({
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "session_id": f"{self.agent_id}-{uuid.uuid4()}",
            "message": json.dumps(payload),   # the record itself is the message
        }).encode()

        req = urllib.request.Request(
            self.endpoint, data=body,
            headers={
                "Content-Type": "application/json",
                "accept": "application/json",
                "x-api-key": self.api_key,
            },
        )
        with urllib.request.urlopen(req) as resp:
            raw = json.loads(resp.read().decode())

        # The agent's reply lives under one of these keys depending on API version.
        text = None
        for key in ("agent_response", "response", "message", "answer"):
            if isinstance(raw, dict) and key in raw:
                text = raw[key]
                break
        if text is None:
            text = raw  # already the payload, or unexpected shape

        # The reply is the triage report as a JSON string; parse it.
        if isinstance(text, str):
            text = text.strip()
            # strip markdown code fences if the model added them
            if text.startswith("```"):
                text = text.split("```")[1] if "```" in text[3:] else text.strip("`")
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text)
        return text


def get_validator(name: str = "local"):
    return LyzrValidator() if name == "lyzr" else LocalValidator()
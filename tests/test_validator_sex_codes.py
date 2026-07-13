import pytest

from app.validator import LocalValidator


def _base(sex: str | None = "M", code: str = "Z34.90"):
    return {
        "encounter": {"encounter_id": "E1", "encounter_date": "2024-06-15",
                      "facility_npi": "1234567890", "provider_npi": "1234567890"},
        "patient": {"patient_id": "P1", "dob": "1990-01-01", "sex": sex, "age": 34},
        "vitals": {}, "diagnoses": [{"code": code, "code_system": "ICD-10-CM"}],
        "procedures": [], "metadata": {},
    }


def _sex_issues(payload):
    return [i for i in LocalValidator().validate(payload)["issues"] if i["field"] == "patient.sex"]


# --- the rule fires on a definite sex ----------------------------------------

def test_pregnancy_code_on_male_is_critical():
    assert any(i["severity"] == "critical" for i in _sex_issues(_base(sex="M")))


def test_prostate_code_on_female_is_critical():
    assert any(i["severity"] == "critical" for i in _sex_issues(_base(sex="F", code="N40.0")))


def test_pregnancy_code_on_female_is_clean():
    assert _sex_issues(_base(sex="F")) == []


@pytest.mark.parametrize("sex", ["m", "male", "Male", " M "])
def test_sex_is_normalized_before_comparison(sex):
    """A casing/spelling variant must not silently skip a critical rule."""
    assert any(i["severity"] == "critical" for i in _sex_issues(_base(sex=sex)))


# --- declining to state sex is never penalized -------------------------------

@pytest.mark.parametrize("sex", ["prefer not to say", "declined", "unknown", "other", "", None])
def test_undeclared_sex_is_never_an_issue(sex):
    """Opting out is a clean value: no critical, no warning, no info, ever."""
    assert _sex_issues(_base(sex=sex)) == []


@pytest.mark.parametrize("sex", ["prefer not to say", "unknown", None])
def test_no_contradiction_asserted_without_a_stated_sex(sex):
    """With no stated sex there is nothing for a sex-restricted code to contradict."""
    assert _sex_issues(_base(sex=sex, code="Z34.90")) == []


def test_missing_sex_does_not_make_the_record_fail():
    p = _base(sex=None, code="J06.9")
    assert LocalValidator().validate(p)["status"] == "pass"


# --- an unrecognized value is an integration defect, not a patient defect -----

def test_unmapped_sex_value_is_info_only():
    issues = _sex_issues(_base(sex="42", code="J06.9"))
    assert [i["severity"] for i in issues] == ["info"]

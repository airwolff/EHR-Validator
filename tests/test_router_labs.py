from app.router import _field_to_domain, route


def test_lab_fields_route_to_clinical():
    assert _field_to_domain("labs[0].resulted") == "clinical"
    assert _field_to_domain("labs[3].ordered") == "clinical"


def test_lab_only_record_is_owned_by_clinical_not_admin():
    """A record whose only defect is a lab must not be filed as an admin problem."""
    report = {
        "status": "fail",
        "issues": [{"field": "labs[0].resulted", "problem": "ordered, never resulted",
                    "severity": "warning", "remediation": "file the result"}],
    }
    assert route(report)["domain"] == "clinical"

from app.validator import LocalValidator


def test_temp_71_2_is_critical(payload_loader):
    """The headline demo evidence: LocalValidator flags temp_f=71.2 as critical.
    Do NOT let a refactor erase this."""
    payload = payload_loader("payload_bad_values.json")
    report = LocalValidator().validate(payload)
    temp_issues = [i for i in report["issues"] if i["field"] == "vitals.temp_f"]
    assert len(temp_issues) == 1
    assert temp_issues[0]["severity"] == "critical"


def test_clean_payload_passes(payload_loader):
    report = LocalValidator().validate(payload_loader("payload_clean.json"))
    assert report["status"] == "pass"
    assert report["issue_count"] == 0

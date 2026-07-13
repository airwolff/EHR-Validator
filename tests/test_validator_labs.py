from app.validator import LocalValidator


def _p(labs):
    return {
        "encounter": {"encounter_id": "E1", "encounter_date": "2024-06-15",
                      "facility_npi": "1234567890", "provider_npi": "1234567890"},
        "patient": {"patient_id": "P1", "dob": "1990-01-01", "sex": "F", "age": 34},
        "vitals": {}, "diagnoses": [], "procedures": [], "metadata": {}, "labs": labs,
    }


def test_ordered_but_not_resulted_warns():
    report = LocalValidator().validate(_p([{"test": "CBC", "value": None,
                                            "ordered": True, "resulted": False}]))
    assert any(i["field"] == "labs[0].resulted" and i["severity"] == "warning"
               for i in report["issues"])


def test_resulted_but_not_ordered_warns():
    report = LocalValidator().validate(_p([{"test": "BMP", "value": 140,
                                            "ordered": False, "resulted": True}]))
    assert any(i["field"] == "labs[0].ordered" for i in report["issues"])


def test_ordered_and_resulted_is_clean():
    report = LocalValidator().validate(_p([{"test": "CBC", "value": 12.1,
                                            "ordered": True, "resulted": True}]))
    assert [i for i in report["issues"] if i["field"].startswith("labs[")] == []


def test_missing_labs_key_is_fine():
    p = _p([])
    del p["labs"]
    report = LocalValidator().validate(p)  # must not raise
    assert isinstance(report["issues"], list)

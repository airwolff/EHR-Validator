"""
EHR Data Quality Triage Agent — Synthetic Payload Generator

Produces two things:

1. Five canonical fixtures (payload_*.json) with KNOWN, distinct errors and
   distinct encounter IDs / source systems. Used for single-record and agent
   testing where you want a predictable answer.

2. A bulk dataset (payloads/encounters.jsonl) sized like one month at a small
   multi-provider clinic — ~1,500 encounters across four source systems and a
   month of weekdays, with randomized error injection. Used to give the SQL
   analytics realistic volume and variation.

Reproducible: fixed --seed means the same data every run, so presentation
numbers stay stable. Change --count or --seed to vary.

Usage:
  python3 generate_payloads.py                 # 5 fixtures + 1500-record bulk
  python3 generate_payloads.py --count 3000    # larger bulk set
  python3 generate_payloads.py --strip-metadata # canonical fixtures without answer key
"""

import argparse
import json
import os
import random
from datetime import date, timedelta

OUTPUT_DIR = "./payloads"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SOURCE_SYSTEMS = [
    {"name": "Epic",         "weight": 0.45, "defect_rate": 0.18},
    {"name": "Cerner",       "weight": 0.25, "defect_rate": 0.30},
    {"name": "athenahealth", "weight": 0.20, "defect_rate": 0.28},
    {"name": "MEDITECH",     "weight": 0.10, "defect_rate": 0.42},
]

FIRST_NAMES = ["Maria", "James", "Linda", "Robert", "Patricia", "John", "Jennifer",
               "Michael", "Susan", "David", "Karen", "Thomas", "Nancy", "Chen",
               "Aisha", "Diego", "Fatima", "Liam", "Priya", "Omar", "Grace", "Noah"]
LAST_NAMES = ["Santos", "Nguyen", "Smith", "Johnson", "Patel", "Garcia", "Kim",
              "Brown", "Okafor", "Rossi", "Muller", "Haddad", "Cohen", "Reyes",
              "Novak", "Ali", "Walsh", "Ivanov", "Torres", "Dubois", "Park"]

ICD10_VALID = ["J06.9", "Z23", "E11.9", "I10", "M54.5", "J45.909", "K21.9",
               "N39.0", "R51", "F41.1", "E78.5", "J02.9"]
CPT_VALID = ["99213", "99214", "99203", "99385", "90471", "85025", "80053",
             "93000", "36415", "99396"]


def _rng_choice_weighted(rng, items, weight_key="weight"):
    r = rng.random()
    cum = 0.0
    for it in items:
        cum += it[weight_key]
        if r <= cum:
            return it
    return items[-1]


def _canonical_base(encounter_id, source_system):
    return {
        "encounter": {
            "encounter_id": encounter_id,
            "encounter_date": "2024-06-15",
            "encounter_type": "outpatient",
            "facility_npi": "1234567890",
            "provider_npi": "0987654321"
        },
        "patient": {
            "patient_id": "PT-884421", "first_name": "Maria", "last_name": "Santos",
            "dob": "1978-03-22", "age": 46, "sex": "F", "zip": "04841"
        },
        "vitals": {
            "height_in": 65, "weight_lbs": 148, "systolic_bp": 118, "diastolic_bp": 76,
            "heart_rate_bpm": 72, "temp_f": 98.6, "spo2_pct": 98
        },
        "diagnoses": [
            {"code": "J06.9", "description": "Acute URI, unspecified", "code_system": "ICD-10-CM"},
            {"code": "Z23", "description": "Encounter for immunization", "code_system": "ICD-10-CM"}
        ],
        "procedures": [
            {"code": "99213", "description": "Office visit, established patient", "code_system": "CPT"}
        ],
        "metadata": {
            "source_system": source_system,
            "extract_timestamp": "2024-06-15T18:32:00Z", "schema_version": "2.1"
        }
    }


def canonical_fixtures():
    fixtures = []

    r = _canonical_base("ENC-20240615-00412", "Epic")
    fixtures.append(("clean", r, []))

    r = _canonical_base("ENC-20240617-00518", "Cerner")
    del r["patient"]["patient_id"]; del r["patient"]["dob"]; del r["encounter"]["facility_npi"]
    fixtures.append(("missing_fields", r, [
        "patient.patient_id removed", "patient.dob removed", "encounter.facility_npi removed"]))

    r = _canonical_base("ENC-20240618-00639", "athenahealth")
    r["encounter"]["encounter_date"] = "06/15/2024"
    r["patient"]["dob"] = "22-03-1978"
    r["metadata"]["extract_timestamp"] = "2024-06-15 18:32:00"
    fixtures.append(("bad_dates", r, [
        "encounter.encounter_date: '06/15/2024' — not YYYY-MM-DD",
        "patient.dob: '22-03-1978' — not ISO 8601",
        "metadata.extract_timestamp: missing T separator and Z suffix"]))

    r = _canonical_base("ENC-20240619-00744", "MEDITECH")
    r["patient"]["age"] = -5
    r["vitals"]["systolic_bp"] = 310
    r["vitals"]["spo2_pct"] = 112
    r["vitals"]["heart_rate_bpm"] = 0
    r["vitals"]["temp_f"] = 71.2
    fixtures.append(("bad_values", r, [
        "patient.age: -5 — negative age",
        "vitals.systolic_bp: 310 — exceeds plausible range; near-certain data-entry error",
        "vitals.spo2_pct: 112 — above 100%, impossible",
        "vitals.heart_rate_bpm: 0 — not a valid vital for a live encounter",
        "vitals.temp_f: 71.2 — implausible for a routine encounter; near-certain data-entry error"]))

    r = _canonical_base("ENC-20240620-00851", "Epic")
    r["diagnoses"][0]["code"] = "J069"
    r["diagnoses"][1]["code"] = "Z2300"
    r["procedures"][0]["code"] = "9921"
    r["procedures"][0]["code_system"] = "cpt"
    fixtures.append(("bad_codes", r, [
        "diagnoses[0].code: 'J069' — missing decimal (should be J06.9)",
        "diagnoses[1].code: 'Z2300' — extra digits, invalid ICD-10 format",
        "procedures[0].code: '9921' — CPT must be exactly 5 digits",
        "procedures[0].code_system: 'cpt' — lowercase, should be 'CPT'"]))

    return fixtures


def _random_clean(rng, seq, enc_date, source_system):
    age = rng.randint(1, 95)
    birth_year = enc_date.year - age
    dob = date(birth_year, rng.randint(1, 12), rng.randint(1, 28))
    enc_id = f"ENC-{enc_date.strftime('%Y%m%d')}-{seq:05d}"
    n_dx = rng.randint(1, 3)
    n_px = rng.randint(1, 2)
    return {
        "encounter": {
            "encounter_id": enc_id,
            "encounter_date": enc_date.strftime("%Y-%m-%d"),
            "encounter_type": rng.choice(["outpatient", "office", "telehealth"]),
            "facility_npi": str(rng.randint(1000000000, 1999999999)),
            "provider_npi": str(rng.randint(1000000000, 1999999999)),
        },
        "patient": {
            "patient_id": f"PT-{rng.randint(100000, 999999)}",
            "first_name": rng.choice(FIRST_NAMES),
            "last_name": rng.choice(LAST_NAMES),
            "dob": dob.strftime("%Y-%m-%d"),
            "age": age,
            "sex": rng.choice(["M", "F"]),
            "zip": f"{rng.randint(1000, 99999):05d}",
        },
        "vitals": {
            "height_in": rng.randint(58, 76),
            "weight_lbs": rng.randint(90, 260),
            "systolic_bp": rng.randint(105, 140),
            "diastolic_bp": rng.randint(65, 88),
            "heart_rate_bpm": rng.randint(58, 96),
            "temp_f": round(rng.uniform(97.4, 99.4), 1),
            "spo2_pct": rng.randint(96, 100),
        },
        "diagnoses": [
            {"code": rng.choice(ICD10_VALID), "description": "dx", "code_system": "ICD-10-CM"}
            for _ in range(n_dx)
        ],
        "procedures": [
            {"code": rng.choice(CPT_VALID), "description": "px", "code_system": "CPT"}
            for _ in range(n_px)
        ],
        "metadata": {
            "source_system": source_system,
            "extract_timestamp": enc_date.strftime("%Y-%m-%dT") +
                f"{rng.randint(8,18):02d}:{rng.randint(0,59):02d}:{rng.randint(0,59):02d}Z",
            "schema_version": "2.1",
        },
    }


def _inj_missing_required(rng, rec):
    field = rng.choice([
        ("patient", "patient_id"), ("patient", "dob"), ("patient", "sex"),
        ("encounter", "facility_npi"), ("encounter", "provider_npi"),
        ("encounter", "encounter_id"),
    ])
    rec[field[0]].pop(field[1], None)


def _inj_bad_date(rng, rec):
    which = rng.choice(["encounter_date", "dob", "timestamp"])
    if which == "encounter_date":
        rec["encounter"]["encounter_date"] = "06/15/2024"
    elif which == "dob":
        rec["patient"]["dob"] = "22-03-1978"
    else:
        rec["metadata"]["extract_timestamp"] = "2024-06-15 18:32:00"


def _inj_bad_value(rng, rec):
    which = rng.choice(["age", "systolic", "spo2", "hr", "temp"])
    if which == "age":
        rec["patient"]["age"] = rng.choice([-5, -1, 130, 200])
    elif which == "systolic":
        rec["vitals"]["systolic_bp"] = rng.choice([310, 320, 45, 210])
    elif which == "spo2":
        rec["vitals"]["spo2_pct"] = rng.choice([112, 105, 60])
    elif which == "hr":
        rec["vitals"]["heart_rate_bpm"] = rng.choice([0, 310, 15])
    else:
        rec["vitals"]["temp_f"] = rng.choice([71.2, 89.0, 110.5])


def _inj_bad_code(rng, rec):
    if rec["diagnoses"] and rng.random() < 0.6:
        rec["diagnoses"][0]["code"] = rng.choice(["J069", "Z2300", "XYZ", "1123"])
    elif rec["procedures"]:
        rec["procedures"][0]["code"] = rng.choice(["9921", "992130", "ABCDE"])


def _inj_bad_code_system(rng, rec):
    if rec["procedures"]:
        rec["procedures"][0]["code_system"] = rng.choice(["cpt", "Cpt", "CPT4"])
    elif rec["diagnoses"]:
        rec["diagnoses"][0]["code_system"] = rng.choice(["icd-10-cm", "ICD10"])


INJECTORS = [_inj_missing_required, _inj_bad_date, _inj_bad_value,
             _inj_bad_code, _inj_bad_code_system]


def generate_bulk(rng, count, start_date):
    weekdays = []
    d = start_date
    while len(weekdays) < 22:
        if d.weekday() < 5:
            weekdays.append(d)
        d += timedelta(days=1)

    records = []
    per_day_seq = {wd: 1 for wd in weekdays}
    for _ in range(count):
        enc_date = rng.choice(weekdays)
        source = _rng_choice_weighted(rng, SOURCE_SYSTEMS)
        seq = per_day_seq[enc_date]
        per_day_seq[enc_date] += 1
        rec = _random_clean(rng, seq, enc_date, source["name"])
        if rng.random() < source["defect_rate"]:
            n_defects = rng.choices([1, 2, 3], weights=[0.6, 0.3, 0.1])[0]
            for inj in rng.sample(INJECTORS, n_defects):
                inj(rng, rec)
        records.append(rec)
    return records


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic EHR payloads.")
    parser.add_argument("--count", type=int, default=1500, help="Bulk record count.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility.")
    parser.add_argument("--start-date", default="2024-06-03", help="Bulk start date YYYY-MM-DD.")
    parser.add_argument("--strip-metadata", action="store_true",
                        help="Drop answer-key keys from canonical fixtures.")
    args = parser.parse_args()

    print(f"Writing canonical fixtures to {OUTPUT_DIR}/")
    for name, payload, errors in canonical_fixtures():
        out = dict(payload)
        if not args.strip_metadata:
            out["_variant"] = name
            out["_injected_errors"] = errors
        with open(f"{OUTPUT_DIR}/payload_{name}.json", "w") as f:
            json.dump(out, f, indent=2)
        status = "CLEAN" if not errors else f"{len(errors)} error(s)"
        print(f"  payload_{name}.json  [{status}]  id={payload['encounter']['encounter_id']}  src={payload['metadata']['source_system']}")

    rng = random.Random(args.seed)
    start = date.fromisoformat(args.start_date)
    records = generate_bulk(rng, args.count, start)
    bulk_path = f"{OUTPUT_DIR}/encounters.jsonl"
    with open(bulk_path, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    by_src = {}
    for rec in records:
        s = rec["metadata"]["source_system"]
        by_src[s] = by_src.get(s, 0) + 1
    print(f"\nWrote {len(records)} bulk encounters to {bulk_path}")
    print("  by source system:", ", ".join(f"{k}={v}" for k, v in sorted(by_src.items())))
    print(f"  seed={args.seed}  start={args.start_date}  (reproducible)")


if __name__ == "__main__":
    main()
"""Generate the synthetic month the month-end auditor audits: 2026-06, 40 records.

Committed INSTEAD of the data (payloads/ is gitignored): same SEED, same 40 files,
byte for byte — that determinism is what makes the audit replayable and gradable.

Planted patterns (the answer key lives in scripts/audit_answer_key.json):
1. unit_conversion_meditech — MEDITECH sends Celsius in temp_f from Jun 15 on.
2. copy_paste_note          — one counseling fragment across 5 unrelated patients.
3. gender_tone_bias         — 4 matched chest-pain pairs; her note dismissive, his workup.
4. race_missing_zip         — Black patients' zip missing ~60% vs ~8% baseline.

Everything else is ordinary: mostly clean records plus routine rule-catchable defects,
so the month looks like a month and not like a puzzle box.
"""
import argparse
import json
import os
import random

SEED = 20260601
N = 40
SYSTEMS = ["Epic", "Cerner", "MEDITECH"]
RACES = ["White", "Black", "Hispanic", "Asian"]
FIRST = {"F": ["Maria", "Ruth", "Keisha", "Ana", "Mei", "Susan", "Dana", "Priya"],
         "M": ["James", "Marcus", "Luis", "Wei", "Robert", "Ahmed", "Peter", "Karl"]}
LAST = ["Smith", "Johnson", "Rivera", "Chen", "Okafor", "Patel", "Brown", "Nguyen"]

COPY_PASTE = [
    "Patient counseled on medication adherence and advised to follow up in two weeks.",
    "Counseled the patient on medication adherence; follow up in two weeks advised.",
    "Patient was counseled regarding medication adherence and told to follow up in two weeks.",
    "Medication adherence counseling provided, follow-up in two weeks.",
    "Counseled on adherence to medications and advised follow-up in two weeks.",
]

TONE_F = ("presents with chest pain. Patient appears anxious and insists something is "
          "wrong. Poor historian, reassurance provided. Advised rest and stress reduction.")
TONE_M = ("presents with chest pain. Cardiac workup ordered: EKG and troponin obtained. "
          "Will admit for observation pending results.")

ORDINARY = [
    "presents for routine follow-up. Vitals stable, no acute complaints. Continue current plan.",
    "seen for medication refill. Reports feeling well. No changes made today.",
    "follow-up for hypertension. Blood pressure at goal, no dizziness or headache.",
    "annual wellness visit. No concerns raised. Screening labs ordered.",
    "presents with seasonal allergies. Symptomatic care advised.",
]


def make_record(i, rng):
    n = i + 1
    sex = rng.choice(["F", "M"])
    race = RACES[i % 4]                      # even spread, deterministic
    day = rng.randint(1, 28)
    date = f"2026-06-{day:02d}"
    system = SYSTEMS[i % 3]
    age = rng.randint(22, 88)
    temp = round(rng.uniform(97.0, 99.4), 1)

    # Plant 1: MEDITECH goes Celsius mid-month.
    if system == "MEDITECH":
        date = f"2026-06-{rng.randint(15, 28):02d}" if i % 2 else f"2026-06-{rng.randint(1, 14):02d}"
        if date >= "2026-06-15":
            temp = round(rng.uniform(36.0, 39.5), 1)

    # Plant 4: race-correlated zip missingness.
    zip_code = None if (race == "Black" and rng.random() < 0.6) else (
        None if rng.random() < 0.08 else f"0{rng.randint(3900, 4999)}")

    note_body = rng.choice(ORDINARY)
    # Plant 3: four matched chest-pain pairs on fixed indices (stable, seed-independent).
    if i in (2, 12, 22, 32):
        sex, note_body = "F", TONE_F
    elif i in (3, 13, 23, 33):
        sex, note_body = "M", TONE_M
    # Plant 2: the copied fragment across five unrelated patients.
    elif i in (5, 11, 19, 27, 35):
        note_body = rng.choice(ORDINARY) + " " + COPY_PASTE[(5, 11, 19, 27, 35).index(i)]

    first = rng.choice(FIRST[sex])
    return {
        "encounter": {"encounter_id": f"E-M{n:03d}", "encounter_date": date,
                      "encounter_type": "outpatient", "facility_npi": "1234567890",
                      "provider_npi": "0987654321"},
        "patient": {"patient_id": f"PT-M{n:03d}", "first_name": first,
                    "last_name": rng.choice(LAST), "dob": f"{2026 - age}-{rng.randint(1,12):02d}-15",
                    "age": age, "sex": sex, "race": race, "zip": zip_code},
        "vitals": {"height_in": rng.randint(60, 76), "weight_lbs": rng.randint(110, 260),
                   "systolic_bp": rng.randint(100, 150), "diastolic_bp": rng.randint(60, 95),
                   "heart_rate_bpm": rng.randint(55, 100), "temp_f": temp,
                   "spo2_pct": rng.randint(94, 100)},
        "diagnoses": [{"code": "I10", "description": "Essential (primary) hypertension",
                       "code_system": "ICD-10-CM"}],
        "procedures": [{"code": "99213", "description": "Office visit, established patient",
                        "code_system": "CPT"}],
        "labs": [],
        "metadata": {"source_system": system,
                     "extract_timestamp": f"{date}T12:00:00Z", "schema_version": "2.1"},
        "clinical_note": f"{age}-year-old {'woman' if sex == 'F' else 'man'} {note_body}",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="payloads/month")
    args = parser.parse_args()
    rng = random.Random(SEED)
    os.makedirs(args.out, exist_ok=True)
    for i in range(N):
        record = make_record(i, rng)
        path = os.path.join(args.out, f"payload_M{i + 1:03d}.json")
        with open(path, "w") as f:
            json.dump(record, f, indent=2, sort_keys=True)
            f.write("\n")
    print(f"wrote {N} records to {args.out}")


if __name__ == "__main__":
    main()

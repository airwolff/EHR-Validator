"""The two specialist agents: what each one is allowed to see, what we ask it, and how we
read its answer back.

Three things this file pins:

1. **Each specialist sees only its own slice of the record.** The clinical reviewer does not
   get the patient's id; the identity reviewer does not get the vitals. A specialist that
   can see everything will comment on everything, and we get back the deterministic
   validator's job done worse and at a cost.
2. **The message we send is byte-identical for the same records, every time.** Recordings are
   filed under a fingerprint of that text (see transport.py). Anything that varies run to run
   — a clock, a uuid, an unsorted dict — means no replay ever matches, the offline path
   breaks, and a live batch re-pays for records it already recorded.
3. **A reply we cannot read is not a clean bill of health.** An agent that returns prose must
   be countable as broken, not scored as "found nothing".
"""
import copy
import json

import pytest

from app.agents.specialists import (
    SPECIALISTS,
    ResponseUnparseable,
    build_message,
    parse_findings,
    record_ids,
)

NOTE = "Patient afebrile and comfortable. Denies chest pain."

PAYLOAD = {
    "patient": {"patient_id": "P1", "name": "Jane Roe", "sex": "F", "age": 34},
    "encounter": {"encounter_id": "E7", "encounter_date": "2026-07-01"},
    "vitals": {"temp_f": 103.1, "spo2": 98},
    "diagnoses": [{"code": "E11.9", "code_system": "ICD-10"}],
    "labs": [{"name": "potassium", "ordered": True, "resulted": True}],
    "clinical_note": NOTE,
    "metadata": {"source_system": "epic"},
}


def record(run_id=7, payload=None):
    return {"run_id": run_id, "payload": copy.deepcopy(payload or PAYLOAD)}


# --- input slices: each specialist sees only its own business --------------------------

def test_the_clinical_reviewer_sees_the_vitals_but_not_who_the_patient_is():
    sliced = SPECIALISTS["clinical"].slice(PAYLOAD)
    assert sliced["vitals"]["temp_f"] == 103.1
    text = json.dumps(sliced)
    assert "P1" not in text and "Jane Roe" not in text


def test_the_identity_reviewer_sees_who_the_patient_is_but_not_the_vitals():
    sliced = SPECIALISTS["identity"].slice(PAYLOAD)
    assert sliced["patient"]["name"] == "Jane Roe"
    assert "vitals" not in sliced
    assert "103.1" not in json.dumps(sliced)


def test_a_slice_cannot_mutate_the_record_it_was_taken_from():
    """The batch hands the same payload to both specialists. If one of them edits it in
    place, the second reviews a record the first quietly rewrote."""
    payload = copy.deepcopy(PAYLOAD)
    sliced = SPECIALISTS["clinical"].slice(payload)
    sliced["vitals"]["temp_f"] = 0
    assert payload["vitals"]["temp_f"] == 103.1


# --- the message: same records in, same text out --------------------------------------

def test_the_message_carries_the_note_and_the_encounter_id():
    message = build_message(SPECIALISTS["clinical"], [record()])
    assert "E7" in message
    assert NOTE in message


def test_the_note_is_sent_verbatim_because_the_evidence_guard_compares_against_it():
    """Task 6 keeps a finding only if its quote appears in the note. If we reformat the note
    on the way out (strip it, re-wrap it, escape it differently), the model quotes what we
    SENT and the guard compares against what we STORED — real findings would be scored as
    hallucinations."""
    note = "  Temp 103.1F.\n\nDenies chest pain.  "
    payload = copy.deepcopy(PAYLOAD)
    payload["clinical_note"] = note
    message = build_message(SPECIALISTS["clinical"], [record(payload=payload)])
    assert json.dumps(note)[1:-1] in message  # the exact note, JSON-escaped, unaltered


def test_a_record_with_no_encounter_id_still_gets_an_id_the_agent_can_echo():
    """Findings are attached back to a record by the id the agent echoes, and Task 10 drops
    any finding carrying an id that wasn't in the batch. A record sent with `null` therefore
    has EVERY finding about it discarded — while still being stamped as processed, so it
    never comes back. Fall back to the run_id, which every record has by definition."""
    payload = copy.deepcopy(PAYLOAD)
    del payload["encounter"]
    message = build_message(SPECIALISTS["clinical"], [record(run_id=42, payload=payload)])
    assert "run-42" in message
    assert '"encounter_id": null' not in message


def test_record_ids_are_the_encounter_id_when_there_is_one():
    assert record_ids([record(run_id=7)]) == {"E7": 7}


def test_record_ids_fall_back_to_the_run_id_when_there_is_not():
    payload = copy.deepcopy(PAYLOAD)
    del payload["encounter"]
    assert record_ids([record(run_id=42, payload=payload)]) == {"run-42": 42}


def test_the_same_records_always_build_the_same_message(monkeypatch):
    """THE TRAP (docs/decisions.md, Task 8). The message is fingerprinted to find its
    recording. A clock, a uuid, or an unsorted dict inside it means the fingerprint changes
    every run: no replay ever hits, and a live batch pays again for records it already paid
    for."""
    first = build_message(SPECIALISTS["clinical"], [record()])
    second = build_message(SPECIALISTS["clinical"], [record()])
    assert first == second


def test_the_message_does_not_depend_on_the_order_the_records_arrive_in():
    """get_noted_records() makes no ordering promise. Two runs over the same five records in
    a different order must not be two different questions — that would double the recordings
    and double the credits."""
    records = [record(run_id=3), record(run_id=1), record(run_id=2)]
    shuffled = [records[2], records[0], records[1]]
    assert build_message(SPECIALISTS["clinical"], records) == build_message(
        SPECIALISTS["clinical"], shuffled)


def test_the_message_does_not_depend_on_the_key_order_inside_the_payload():
    """Two payloads with identical content but different key insertion order are the same
    question and must fingerprint identically."""
    reversed_keys = {k: PAYLOAD[k] for k in reversed(list(PAYLOAD))}
    assert build_message(SPECIALISTS["clinical"], [record(payload=PAYLOAD)]) == build_message(
        SPECIALISTS["clinical"], [record(payload=reversed_keys)])


def test_the_prompt_lists_the_domains_the_guard_will_accept():
    """We ask the model for a 'domain' and then silently drop any value outside
    schema.VALID_DOMAINS. If we never tell it the vocabulary, a sensible guess ('vitals')
    gets tallied as a malformed finding — OUR under-specified prompt, scored as the model's
    unreliability. Exactly the Task-6 Unicode bug wearing a different hat."""
    from app.agents.schema import VALID_DOMAINS, VALID_SEVERITIES

    for specialist in SPECIALISTS.values():
        prompt = specialist.system_prompt()
        for domain in VALID_DOMAINS:
            assert domain in prompt, f"{specialist.name} prompt never mentions domain {domain}"
        for severity in VALID_SEVERITIES:
            assert severity in prompt


def test_the_prompt_defines_every_field_it_demands():
    """Fields we ask for but never define come back as junk that the guard then rejects."""
    prompt = SPECIALISTS["clinical"].system_prompt().lower()
    for field in ("adjudication", "confidence", "owner", "remediation"):
        # asked for in the shape AND explained somewhere after it
        assert prompt.count(field) >= 2, f"{field} is demanded but never explained"


def test_the_prompt_tells_the_model_the_note_is_data_not_instructions():
    prompt = SPECIALISTS["clinical"].system_prompt()
    assert "DATA" in prompt and "never obey" in prompt.lower()


def test_the_clinical_specialist_is_told_not_to_redo_the_validators_job():
    """The thesis: rules do ranges, the LLM does what rules cannot reach. A specialist that
    re-checks numeric bounds is an expensive, unreliable copy of validator.py."""
    prompt = SPECIALISTS["clinical"].system_prompt().lower()
    assert "contradict" in prompt
    assert "do not re-check" in prompt


# --- reading the answer back ----------------------------------------------------------

def test_a_plain_json_answer_parses():
    assert parse_findings('{"findings": [{"field": "vitals.temp_f"}]}') == [
        {"field": "vitals.temp_f"}]


def test_an_answer_wrapped_in_code_fences_parses():
    """Models wrap JSON in ```json fences constantly, contract or no contract."""
    raw = '```json\n{"findings": [{"field": "vitals.temp_f"}]}\n```'
    assert parse_findings(raw) == [{"field": "vitals.temp_f"}]


def test_an_answer_that_is_a_bare_list_of_findings_parses():
    """The contract asks for {"findings": [...]}, but a model that returns just the list is
    being understood, not obeyed. Accept it — the schema guard checks each finding anyway."""
    assert parse_findings('[{"field": "vitals.temp_f"}]') == [{"field": "vitals.temp_f"}]


def test_an_empty_findings_list_is_a_real_answer_meaning_nothing_is_wrong():
    assert parse_findings('{"findings": []}') == []


def test_a_correct_answer_wrapped_in_chatter_still_parses():
    """Models say 'Here are the findings:' before the JSON constantly, contract or no
    contract. Throwing that away as 'unreadable' would inflate the LLM-failure rate we
    report — in our own favour, which is a number we would have to retract."""
    raw = 'Here are the findings:\n```json\n{"findings": [{"field": "vitals.temp_f"}]}\n```\nLet me know!'
    assert parse_findings(raw) == [{"field": "vitals.temp_f"}]


def test_an_answer_with_json_but_no_fences_and_some_chatter_still_parses():
    raw = 'Sure. {"findings": [{"field": "patient.age"}]} Hope that helps.'
    assert parse_findings(raw) == [{"field": "patient.age"}]


def test_an_unreadable_answer_raises_instead_of_looking_like_a_clean_record():
    """The important one. If prose parsed to [], a permanently broken agent would score as a
    PERFECT agent — it never reports a false finding and never misses one, because it never
    says anything. Task 13's miss-rate would be measuring nothing."""
    for junk in ("I'm sorry, I can't help with that.", "", "{truncated", "null"):
        with pytest.raises(ResponseUnparseable):
            parse_findings(junk)


def test_the_unreadable_answer_is_included_in_the_error_so_it_can_be_looked_at():
    with pytest.raises(ResponseUnparseable) as exc:
        parse_findings("I'm sorry, I can't help with that.")
    assert "sorry" in str(exc.value)


def test_a_huge_unreadable_answer_is_truncated_in_the_error():
    """The reply can be kilobytes of model output with the chart echoed back inside it. That
    should not land whole in a log, a traceback, or a screenshot."""
    with pytest.raises(ResponseUnparseable) as exc:
        parse_findings("I am so sorry. " * 500)
    assert len(str(exc.value)) < 400

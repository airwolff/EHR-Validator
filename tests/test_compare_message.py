"""The comparison message is a pure function of (try number, records): same try number,
same bytes — that is what lets a saved reply be found again. And the rotation is fair:
across 5 tries every record appears in every position exactly once."""
import pytest

from app.agents import compare
from app.agents.transport import fingerprint


@pytest.fixture
def payloads(payload_loader):
    return {rid: payload_loader(rid + ".json") for rid in compare.CANONICAL_RECORD_IDS}


def test_same_try_number_gives_byte_identical_message(payloads):
    assert (compare.build_comparison_message(3, payloads)
            == compare.build_comparison_message(3, payloads))


def test_each_try_number_gives_a_distinct_fingerprint(payloads):
    prints = {fingerprint(compare.build_comparison_message(n, payloads))
              for n in range(1, 6)}
    assert len(prints) == 5  # five tries, five recordings, no collisions


def test_rotation_is_fair():
    orders = [compare.run_order(n) for n in range(1, 6)]
    for order in orders:  # every try sends all 5 records, each exactly once
        assert sorted(order) == compare.CANONICAL_RECORD_IDS
    for position in range(5):  # every record leads/anchors each position once
        assert ({order[position] for order in orders}
                == set(compare.CANONICAL_RECORD_IDS))


def test_try_number_outside_1_to_5_is_refused():
    for bad in (0, 6, -1):
        with pytest.raises(ValueError):
            compare.run_order(bad)


def test_message_carries_instructions_and_every_record(payloads):
    msg = compare.build_comparison_message(1, payloads)
    assert "critical|warning|info" in msg           # severity ladder, from the constants
    assert "data-quality validator" in msg
    for rid in compare.CANONICAL_RECORD_IDS:
        assert rid in msg                            # every record id present


def test_missing_fixture_is_refused(payloads):
    del payloads["payload_clean"]
    with pytest.raises(ValueError):
        compare.build_comparison_message(1, payloads)


def test_load_fixtures_returns_exactly_the_five_canonical():
    payloads = compare.load_fixtures()
    assert sorted(payloads) == compare.CANONICAL_RECORD_IDS
    # and NOT the two noted demo fixtures that share the folder
    assert "payload_wrong_patient_note" not in payloads

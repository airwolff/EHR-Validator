"""The credit ledger: a hard, persisted cap on live Lyzr calls.

The ledger is the only thing standing between a runaway loop and a real bill. Every test
here is about it failing CLOSED: when in doubt, refuse the call. A ledger that fails open
is worse than no ledger, because it is trusted.
"""
import json
import os

import pytest

from app.agents.ledger import (
    DEFAULT_MONTHLY_BUDGET,
    BudgetExceeded,
    CreditLedger,
    LedgerCorrupt,
    current_month,
)


def ledger(tmp_path, budget=20, month="2026-07"):
    return CreditLedger(str(tmp_path / "ledger.json"), budget=budget, month=month)


# --- spending -------------------------------------------------------------------------

def test_spend_increments_and_persists_across_processes(tmp_path):
    """A fresh CreditLedger over the same file must see the earlier spend. If it doesn't,
    every run starts at zero and the cap means nothing."""
    ledger(tmp_path).spend()
    assert ledger(tmp_path).spent() == 1


def test_spend_refuses_past_budget_and_the_refused_call_does_not_count(tmp_path):
    led = ledger(tmp_path, budget=2)
    led.spend()
    led.spend()
    with pytest.raises(BudgetExceeded):
        led.spend()
    assert led.spent() == 2
    assert led.remaining() == 0


def test_an_oversized_spend_is_refused_whole_not_partially(tmp_path):
    """spend(5) against 3 remaining must buy nothing — not clamp to 3. A partial spend
    would report success for a batch that never fully ran."""
    led = ledger(tmp_path, budget=3)
    with pytest.raises(BudgetExceeded):
        led.spend(5)
    assert led.spent() == 0


def test_spend_of_zero_or_less_is_a_programming_error(tmp_path):
    """Refuse the refund path outright: spend(-5) would silently hand credits back."""
    led = ledger(tmp_path)
    for n in (0, -1):
        with pytest.raises(ValueError):
            led.spend(n)
    assert led.spent() == 0


def test_a_fractional_spend_is_refused_before_it_reaches_the_file(tmp_path):
    """The self-bricking bug: spend(1.5) passes an `n < 1` guard, writes 1.5 to disk, and
    from then on EVERY read is LedgerCorrupt — the ledger locks out all live calls until a
    human hand-edits it. Reject the float at the door."""
    led = ledger(tmp_path)
    with pytest.raises(ValueError):
        led.spend(1.5)
    with pytest.raises(ValueError):
        led.spend(True)  # bool is an int subclass; not a credit count
    assert led.spent() == 0


def test_a_concurrent_spender_cannot_slip_past_the_cap(tmp_path):
    """spend() is read-modify-write. Without a lock, two processes both read 14/15, both
    decide there is room, and both write 15: two credits spent, one recorded. The gate in
    front of real money must not be off by one per race."""
    import threading

    p = str(tmp_path / "ledger.json")
    barrier = threading.Barrier(8)
    granted = []

    def worker():
        led = CreditLedger(p, budget=4, month="2026-07")
        barrier.wait()  # maximise the overlap on the read-modify-write
        try:
            led.spend()
            granted.append(1)
        except BudgetExceeded:
            pass

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert sum(granted) == 4, "the cap let more spenders through than the budget allows"
    assert CreditLedger(p, budget=4, month="2026-07").spent() == 4


# --- monthly buckets ------------------------------------------------------------------

def test_each_month_gets_its_own_budget(tmp_path):
    """Lyzr's allowance resets monthly. A lifetime counter would block a fresh month while
    the vendor is happily serving."""
    july = ledger(tmp_path, budget=2, month="2026-07")
    july.spend(2)
    with pytest.raises(BudgetExceeded):
        july.spend()

    august = ledger(tmp_path, budget=2, month="2026-08")
    assert august.spent() == 0
    august.spend()
    assert august.remaining() == 1


def test_spending_a_new_month_preserves_the_old_months_record(tmp_path):
    """The ledger is also the audit trail — 'we made N live calls in July' is a portfolio
    number. A new month must not clobber it."""
    ledger(tmp_path, month="2026-07").spend(3)
    ledger(tmp_path, month="2026-08").spend(1)
    assert ledger(tmp_path, month="2026-07").spent() == 3
    assert ledger(tmp_path, month="2026-08").spent() == 1


def test_current_month_is_a_yyyy_mm_key():
    assert len(current_month()) == 7
    year, month = current_month().split("-")
    assert year.isdigit() and 1 <= int(month) <= 12


def test_a_malformed_month_key_is_rejected_not_quietly_given_its_own_budget(tmp_path):
    """"2026-7" is not "2026-07". Unvalidated, it opens a SECOND full-budget bucket inside
    the same calendar month — the cap silently doubles."""
    for bad in ("2026-7", "July", "2026", "2026-13", ""):
        with pytest.raises(ValueError):
            CreditLedger(str(tmp_path / "l.json"), budget=20, month=bad)


# --- failing closed -------------------------------------------------------------------

def test_a_corrupt_ledger_refuses_calls_rather_than_reading_as_zero(tmp_path):
    """The dangerous bug: a truncated file that json.load can't parse being swallowed and
    treated as 'nothing spent yet', re-opening the full budget on every corrupt read."""
    p = tmp_path / "ledger.json"
    p.write_text('{"months": {"2026-07": 4')  # truncated mid-write
    led = CreditLedger(str(p), budget=20, month="2026-07")
    with pytest.raises(LedgerCorrupt):
        led.spent()
    with pytest.raises(LedgerCorrupt):
        led.spend()


def test_a_ledger_with_a_non_integer_count_is_corrupt_not_zero(tmp_path):
    p = tmp_path / "ledger.json"
    p.write_text('{"months": {"2026-07": "lots"}}')
    with pytest.raises(LedgerCorrupt):
        CreditLedger(str(p), budget=20, month="2026-07").spent()


def test_a_missing_ledger_file_is_simply_a_fresh_month(tmp_path):
    """Absent != corrupt. First run must work without a bootstrap step."""
    led = CreditLedger(str(tmp_path / "nope.json"), budget=20, month="2026-07")
    assert led.spent() == 0
    assert led.remaining() == 20


def test_the_ledger_file_is_never_left_truncated(tmp_path):
    """Written via a temp file + atomic replace, so a crash mid-write cannot leave a
    half-file that the next run has to call corrupt."""
    p = tmp_path / "ledger.json"
    led = CreditLedger(str(p), budget=20, month="2026-07")
    led.spend()
    assert json.loads(p.read_text()) == {"months": {"2026-07": 1}}
    # The lock file is expected and stays; a leftover .ledger-*.tmp is not.
    leftovers = [f for f in os.listdir(tmp_path) if f.startswith(".ledger-")]
    assert leftovers == []


# --- budget from the environment ------------------------------------------------------

def test_budget_defaults_to_the_free_tier_safe_value(tmp_path, monkeypatch):
    """No env var set must not mean 'unlimited', and must not assume the paid plan: the
    default has to be survivable on the 20-credit free tier."""
    monkeypatch.delenv("LYZR_CREDIT_BUDGET", raising=False)
    led = CreditLedger(str(tmp_path / "l.json"), month="2026-07")
    assert led.budget == DEFAULT_MONTHLY_BUDGET
    assert DEFAULT_MONTHLY_BUDGET < 20


def test_budget_comes_from_the_environment_when_set(tmp_path, monkeypatch):
    monkeypatch.setenv("LYZR_CREDIT_BUDGET", "200")
    assert CreditLedger(str(tmp_path / "l.json"), month="2026-07").budget == 200


def test_an_unparseable_budget_raises_rather_than_falling_back(tmp_path, monkeypatch):
    """A typo'd cap must not quietly become the default — you'd think you were capped at
    200 and be capped at 15, or vice versa."""
    monkeypatch.setenv("LYZR_CREDIT_BUDGET", "two hundred")
    with pytest.raises(ValueError):
        CreditLedger(str(tmp_path / "l.json"), month="2026-07")


def test_an_explicit_budget_argument_beats_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("LYZR_CREDIT_BUDGET", "200")
    assert CreditLedger(str(tmp_path / "l.json"), budget=5, month="2026-07").budget == 5

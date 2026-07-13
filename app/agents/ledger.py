"""A hard, persisted cap on live Lyzr calls.

Every live agent call costs a real credit. Tests, replays and dry runs must cost nothing;
this ledger is what makes that a guarantee rather than a habit. It is the only gate in
front of the money, so its single design rule is: **fail closed**. Cannot read the file →
refuse. Count isn't an integer → refuse. Budget string is junk → refuse. A ledger that
guesses "probably zero spent" hands the full budget back on every corrupt read, and it
does so silently, which is worse than having no ledger at all — because this one is
trusted.

Buckets are per calendar month ("2026-07"), because that is how Lyzr's allowance resets.
A lifetime counter would eventually block a fresh billing month while the vendor was
happily serving. Old months are kept, never pruned: "we made N live calls in July" is the
spend record.

The cap survived the upgrade from the 20-credit free tier to Starter's 2,000 on purpose.
A spend gate is correct engineering at any budget, and the default here stays
free-tier-safe so cancelling the subscription needs no code change.
"""
import fcntl
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime

MONTH_KEY = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

# Survivable on the 20-credit free tier. While on Starter, set LYZR_CREDIT_BUDGET in .env.
# Deliberately not the paid allowance: if the subscription lapses, the safe number is
# already in force and nobody has to remember to lower it.
DEFAULT_MONTHLY_BUDGET = 15

BUDGET_ENV_VAR = "LYZR_CREDIT_BUDGET"


class LedgerError(RuntimeError):
    """Base for every reason a live call must not happen. Callers gate on this."""


class BudgetExceeded(LedgerError):
    """The call would spend more credits than the month's budget allows."""


class LedgerCorrupt(LedgerError):
    """The ledger file exists but cannot be trusted. Refuse rather than assume zero."""


def current_month():
    """The current bucket key, "YYYY-MM"."""
    return datetime.now().strftime("%Y-%m")


def _budget_from_env():
    raw = os.environ.get(BUDGET_ENV_VAR)
    if raw is None or not raw.strip():
        return DEFAULT_MONTHLY_BUDGET
    try:
        budget = int(raw)
    except ValueError:
        raise ValueError(
            f"{BUDGET_ENV_VAR}={raw!r} is not an integer. Refusing to guess a credit cap."
        ) from None
    if budget < 0:
        raise ValueError(f"{BUDGET_ENV_VAR}={raw!r} is negative.")
    return budget


class CreditLedger:
    """Counts live Lyzr calls against a monthly budget, persisted to a JSON file.

    File shape: {"months": {"2026-07": 12}}

    `month` is injectable so tests never depend on the wall clock; leave it None in
    production and it tracks the real calendar.
    """

    def __init__(self, path, budget=None, month=None):
        self.path = path
        self.budget = _budget_from_env() if budget is None else int(budget)
        # `None` means "the real calendar"; "" is a malformed key, not a request for it.
        self.month = current_month() if month is None else month
        # "2026-7" is not "2026-07". Unchecked, a typo'd key opens a SECOND full-budget
        # bucket inside the same calendar month and the cap quietly doubles.
        if not MONTH_KEY.match(str(self.month)):
            raise ValueError(f"month must be YYYY-MM, got {self.month!r}.")

    @contextmanager
    def _exclusive(self):
        """Hold an exclusive lock across the whole read-modify-write.

        spend() reads the count, decides, then writes. Two processes without this lock
        both read 14/15, both decide there is room, and both write 15: two credits spent,
        one recorded — the gate in front of real money, off by one per race. The lock is a
        SEPARATE file because _write swaps the ledger's inode via os.replace; a lock held
        on the old inode would guard nothing.
        """
        lock_path = self.path + ".lock"
        os.makedirs(os.path.dirname(os.path.abspath(lock_path)), exist_ok=True)
        with open(lock_path, "w") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _read_months(self):
        if not os.path.exists(self.path):
            return {}  # Absent is not corrupt: the first run has nothing to read.
        try:
            with open(self.path) as f:
                data = json.load(f)
            months = data["months"]
        except (json.JSONDecodeError, OSError, TypeError, KeyError) as exc:
            raise LedgerCorrupt(
                f"Ledger {self.path} is unreadable ({exc}). Refusing live calls. "
                f"Inspect it, then delete it only if you accept losing the spend record."
            ) from exc
        if not isinstance(months, dict) or any(
            not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in months.values()
        ):
            raise LedgerCorrupt(
                f"Ledger {self.path} holds a non-integer or negative count. Refusing live calls."
            )
        return months

    def spent(self):
        """Credits already spent this month. Raises LedgerCorrupt rather than return 0."""
        return self._read_months().get(self.month, 0)

    def remaining(self):
        return max(0, self.budget - self.spent())

    def spend(self, n=1):
        """Charge `n` credits, or raise. Nothing is charged unless all of `n` fits — a
        partial spend would report success for a batch that never fully ran."""
        # Not just `n < 1`: spend(1.5) would pass that, write 1.5 to disk, and every read
        # afterwards would raise LedgerCorrupt — the ledger bricking itself and locking out
        # all live calls until a human edits the file by hand. bool is an int subclass and
        # is not a credit count.
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise ValueError(
                f"spend(n) needs a whole number >= 1, got {n!r}. Credits are not refundable."
            )
        with self._exclusive():
            months = self._read_months()
            current = months.get(self.month, 0)
            if current + n > self.budget:
                raise BudgetExceeded(
                    f"Live Lyzr call refused: {self.month} spend {current}+{n} would exceed "
                    f"budget {self.budget}. Raise {BUDGET_ENV_VAR} only if the credits are real."
                )
            months[self.month] = current + n
            self._write(months)

    def _write(self, months):
        """Atomic: a crash mid-write must not leave a truncated file that the next run has
        to call corrupt (which would then block every live call until a human intervened).

        The directory is fsynced too, not just the file — otherwise the data is durable but
        the RENAME may not be, and a power loss reverts the ledger to the previous count,
        making already-spent credits spendable again."""
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".ledger-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump({"months": months}, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

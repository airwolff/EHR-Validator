"""Crash-safe file writing, shared by the ledger and the recordings.

Both write files that a later run has to trust: the ledger holds how much real money has
been spent, and a recording stands in for an agent's answer. A write interrupted halfway
(power cut, Ctrl-C, OOM kill) must never leave a half-written file behind, because the next
run cannot tell "truncated" from "that's what it said" — it either refuses to run or, worse,
believes the fragment.

The trick: write the new content to a temporary file, then rename it over the target.
A rename is all-or-nothing at the filesystem level — the target is either the old content or
the new one, never a mix.
"""
import os
import tempfile


def atomic_write_text(path, text):
    """Write `text` to `path` so that a crash can never leave it half-written."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".partial")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())  # push the bytes to disk, not just the OS cache
        os.replace(tmp, path)
        # fsync the DIRECTORY too: without this the bytes are durable but the rename may
        # not be, so a power loss can revert the file to its previous contents.
        dir_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise

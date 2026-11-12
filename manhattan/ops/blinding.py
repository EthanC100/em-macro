"""Outcome blinding by access control: what may leave the runner on a public channel (criteria O-01 to O-03).

em-macro is public: its files, its git history, its Actions logs, step summaries, artifacts and issues can be read
by anyone, including a generator session. Forward and screening performance therefore never goes there in any
form. It is written only to the private ledger (``manhattan-ledger``; ``manhattan.ops.store``), which only the
runner's deploy key can write and which no Claude Code session is given.

What the runner may say in public is a **health record**: operational facts only (counts, coverage, missed days,
failures, hashes). ``health`` checks every key against a fixed schema and every value against its kind; a float, a
free-text string or an unknown key is refused before anything is printed. Free text is never allowed because an
exception message or a formatted number can carry an outcome.

``quiet`` redirects file descriptors 1 and 2 (not just ``sys.stdout``) to a private log for the duration of the
work, so print statements, warnings, C-level output, subprocesses and tracebacks all land in the private clone.
``failure`` turns an exception into what may be said publicly: the stage and the exception's class name.

Limits, stated plainly: this protects the public channels from Manhattan's own code. It does not stop anyone who can
read the private ledger (Ethan can read everything; blinding of humans rests on his discipline), and it does not
stop anyone from recomputing a public-data strategy from public specs and public prices (ARCHITECTURE section 8,
item 3); the generator isolation kit is what keeps a blind generator from doing that.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import secrets
import sys
from pathlib import Path

SCHEMA_VERSION = 1
NONCE_BYTES = 16                       # 128 bits: a published head hash cannot be brute-forced back to an outcome

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_HASH = re.compile(r"^[0-9a-f]{40}$|^[0-9a-f]{64}$")       # a full git commit or a SHA-256; nothing shorter
_WORD = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{0,63}$")      # no dot, no colon, no space: cannot spell a decimal

# every key the public health record may carry, with the kind of its value
HEALTH_SCHEMA = {
    "schema_version": "int", "runner": "word", "run_id": "int", "run_attempt": "int", "commit": "hash",
    "status": "status", "stage": "word", "error_class": "word", "started_utc": "time", "finished_utc": "time",
    "asof": "date", "duration_seconds": "int",
    "ledger_records": "int", "ledger_head": "hash", "ledger_new_records": "int", "chain_ok": "bool",
    "mirror_status": "word", "mirror_head": "hash", "mirror_ok": "bool",
    "journal_reconciled": "int", "journal_unfinished": "int",
    "lock_status": "word", "locks_broken": "int",
    "batches": "int", "predictions_registered": "int", "predictions_eligible": "int",
    "predictions_ineligible": "int", "predictions_provisional": "int",
    "observations_new": "int", "observations_total": "int", "observations_reconstructed": "int",
    "observations_expected": "int", "missed_observations": "int", "missed_runs": "dates", "missed_runs_new": "int",
    "captures_new": "int", "captures_total": "int", "sources_ok": "words", "sources_failed": "words",
    "conflicts": "int", "checkpoints": "words", "promotion": "word",
}
STATUSES = ("ok", "failed", "locked", "partial", "dry_run", "nothing_to_do")


class BlindingError(ValueError):
    """Something that is not operational health was about to be written to a public channel."""


def _check(key: str, kind: str, v) -> str | None:
    if kind == "int":
        ok = isinstance(v, int) and not isinstance(v, bool)
    elif kind == "bool":
        ok = isinstance(v, bool)
    elif kind == "date":
        ok = isinstance(v, str) and bool(_DATE.match(v))
    elif kind == "time":
        ok = isinstance(v, str) and bool(_TIME.match(v))
    elif kind == "hash":
        ok = isinstance(v, str) and bool(_HASH.match(v))
    elif kind == "word":
        ok = isinstance(v, str) and bool(_WORD.match(v))
    elif kind == "status":
        ok = v in STATUSES
    elif kind == "dates":
        ok = isinstance(v, list) and len(v) <= 400 and all(isinstance(x, str) and _DATE.match(x) for x in v)
    elif kind == "words":
        ok = isinstance(v, list) and len(v) <= 400 and all(isinstance(x, str) and _WORD.match(x) for x in v)
    else:                                                      # pragma: no cover - the schema is fixed above
        ok = False
    return None if ok else f"{key}: a value of kind {kind} was expected"


def health(record: dict) -> dict:
    """The record, checked: every key in ``HEALTH_SCHEMA`` and every value of its kind. Raises ``BlindingError``."""
    if not isinstance(record, dict):
        raise BlindingError("a health record is a mapping")
    errs = []
    for k, v in record.items():
        kind = HEALTH_SCHEMA.get(k)
        if kind is None:
            errs.append(f"{k}: not a health field")
            continue
        e = _check(k, kind, v)
        if e:
            errs.append(e)
    if errs:
        # the message names keys only, never the offending value
        raise BlindingError("refused to publish: " + "; ".join(errs))
    return {"schema_version": SCHEMA_VERSION, **record}


def render(record: dict) -> str:
    """One JSON line for a public log, after ``health``."""
    return json.dumps(health(record), sort_keys=True, separators=(",", ":"))


def summary_markdown(record: dict) -> str:
    """The public step summary / issue body: the health record and nothing else."""
    rec = health(record)
    lines = ["### Manhattan ops runner: health", "", "Operational health only. Outcomes are in the private ledger.",
             "", "| field | value |", "|---|---|"]
    for k in sorted(rec):
        v = rec[k]
        lines.append(f"| {k} | {', '.join(v) if isinstance(v, list) else v} |")
    return "\n".join(lines) + "\n"


def failure(stage: str, exc: BaseException) -> dict:
    """What may be said publicly about an exception: the stage and the class name. Never the message."""
    name = type(exc).__name__
    return {"status": "failed", "stage": stage if _WORD.match(stage or "") else "unknown",
            "error_class": name if _WORD.match(name) else "Exception"}


def nonce() -> str:
    """A fresh 128-bit nonce for a private record."""
    return secrets.token_hex(NONCE_BYTES)


@contextlib.contextmanager
def quiet(log_path: Path):
    """Send everything written to file descriptors 1 and 2 to ``log_path`` (private) until the block ends.

    Python-level ``sys.stdout``/``sys.stderr`` are flushed and pointed at the same file, so nothing buffered before
    the redirect leaks after it, and nothing written inside the block reaches the public log."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    sys.stdout.flush()
    sys.stderr.flush()
    saved = os.dup(1), os.dup(2)
    old_py = sys.stdout, sys.stderr
    with open(log_path, "a", encoding="utf-8") as f:
        os.dup2(f.fileno(), 1)
        os.dup2(f.fileno(), 2)
        sys.stdout = sys.stderr = f
        try:
            yield f
        finally:
            f.flush()
            sys.stdout, sys.stderr = old_py
            os.dup2(saved[0], 1)
            os.dup2(saved[1], 2)
            os.close(saved[0])
            os.close(saved[1])


def write_step_summary(record: dict, path: str | os.PathLike | None = None) -> None:
    """Append the health summary to ``$GITHUB_STEP_SUMMARY`` (or ``path``) when there is one."""
    target = path or os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as f:
            f.write(summary_markdown(record))

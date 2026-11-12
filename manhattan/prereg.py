"""Frozen pre-registrations: check a file against its recorded SHA-256.

    python -m manhattan.prereg verify      # exit 1 unless every recorded file matches

A record is a line of ``sha256sum`` output (``<64 hex>  <path from the repository root>``), so
``sha256sum -c docs/manhattan/sim_prereg.sha256`` run from the root gives the same answer. The hash is of the file's
bytes, computed with ``lab.book.sha256`` (the Lab's frozen-file check).

docs/manhattan/SIM_PREREG.md is never edited: additions go to docs/manhattan/SIM_PREREG_AMENDMENTS.md (its section 8.4).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from lab.book import sha256

ROOT = Path(__file__).resolve().parents[1]
RECORDS = (ROOT / "docs/manhattan/sim_prereg.sha256",)
_LINE = re.compile(r"^([0-9a-f]{64}) [ *](\S.*)$")


def read_record(path: Path) -> list[tuple[str, str]]:
    """(hash, relative path) for every line of a ``sha256sum`` file; raises ValueError on a malformed line."""
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        m = _LINE.match(line)
        if not m:
            raise ValueError(f"{path.name} line {n} is not '<sha256>  <path>'")
        out.append((m.group(1), m.group(2).strip()))
    if not out:
        raise ValueError(f"{path.name} records no file")
    return out


def verify(record: Path, root: Path = ROOT) -> list[str]:
    """Problems found (empty when every recorded file exists and matches its hash)."""
    try:
        rows = read_record(record)
    except (OSError, ValueError) as e:
        return [str(e)]
    errs = []
    for want, rel in rows:
        p = root / rel
        if not p.is_file():
            errs.append(f"{rel}: missing")
            continue
        got = sha256(p)
        if got != want:
            errs.append(f"{rel}: SHA-256 is {got}, recorded {want} (a frozen pre-registration is never edited)")
    return errs


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["verify"]:
        print(__doc__)
        return 2
    errs = [e for r in RECORDS for e in verify(r, ROOT)]
    print("\n".join(errs) or "pre-registrations ok")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())

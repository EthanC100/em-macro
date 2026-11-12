"""Version 2 of the simulation pre-registration: check it against its recorded SHA-256.

    python -m manhattan.prereg_v2 verify      # exit 1 unless the v1 record and the v2 record both match

docs/manhattan/SIM_PREREG_v2.md covers only the parts of docs/manhattan/SIM_PREREG.md that changed with Protocol
v3.1 (the hedge-aware SPA test and the analytic hierarchical model). Version 1 stays frozen and in force for
everything else, so this check runs the version 1 check first and then the version 2 record
(``docs/manhattan/sim_prereg_v2.sha256``, a line of ``sha256sum`` output).

``manhattan/prereg.py`` is a protected file and is not edited by a session; this module sits beside it and
reuses its functions. docs/manhattan/ETHAN_ACTIONS.md item 19 lists the CODEOWNERS lines that protect this
module, its test and the files it checks once Ethan adopts them.
"""
from __future__ import annotations

import sys
from pathlib import Path

from manhattan import prereg

ROOT = prereg.ROOT
SIM_PREREG_V2 = "docs/manhattan/SIM_PREREG_v2.md"
PROTOCOL_V31 = "docs/manhattan/PROTOCOL_v3.1.md"
RECORD = ROOT / "docs/manhattan/sim_prereg_v2.sha256"


def verify(root: Path = ROOT) -> list[str]:
    """Problems found in either record (empty when every recorded file exists and matches its hash)."""
    records = dict.fromkeys(r.relative_to(prereg.ROOT) for r in (*prereg.RECORDS, RECORD))      # each record once
    return [e for r in records for e in prereg.verify(root / r, root)]


def recorded_hash(rel: str, root: Path = ROOT) -> str:
    """The recorded SHA-256 of ``rel`` in the v2 record, after checking that the file still matches it."""
    record = root / RECORD.relative_to(ROOT)
    errs = prereg.verify(record, root)
    if errs:
        raise RuntimeError("version 2 of the simulation pre-registration does not match its recorded hash: "
                           + "; ".join(errs))
    for h, path in prereg.read_record(record):
        if path == rel:
            return h
    raise RuntimeError(f"{rel} is not in {record.name}")


def prereg_v2_hash(root: Path = ROOT) -> str:
    return recorded_hash(SIM_PREREG_V2, root)


def protocol_v31_hash(root: Path = ROOT) -> str:
    return recorded_hash(PROTOCOL_V31, root)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["verify"]:
        print(__doc__)
        return 2
    errs = verify()
    print("\n".join(errs) or "pre-registrations ok (v1 and v2)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())

"""T02 step 1: verify the re-downloaded raw macro vintages against the committed manifest.

    python -m em_macro.t02_verify        # -> results/T02/raw_data_verification.csv; exit 1 on any difference

Compares every file listed in results/T02/raw_data_manifest.csv (written at the data-feasibility step,
2026-11-03) with the file now in data/raw/econ_momentum/: present or missing, byte size, SHA-256.  Files
present on disk but not in the manifest are listed as extra.  Nothing is computed from the data.
"""
from __future__ import annotations

import hashlib
import sys

import pandas as pd

from .config import RAW, RESULTS, ROOT

MANIFEST = RESULTS / "T02" / "raw_data_manifest.csv"
OUTFILE = RESULTS / "T02" / "raw_data_verification.csv"
RAWDIR = RAW / "econ_momentum"


def verify() -> pd.DataFrame:
    man = pd.read_csv(MANIFEST)
    rows = []
    for r in man.itertuples(index=False):
        p = ROOT / r.file
        if not p.exists():
            rows.append({"file": r.file, "status": "missing", "bytes_manifest": r.bytes, "bytes_now": None,
                         "sha256_manifest": r.sha256, "sha256_now": None})
            continue
        b = p.read_bytes()
        h = hashlib.sha256(b).hexdigest()
        rows.append({"file": r.file, "status": "ok" if (h == r.sha256 and len(b) == r.bytes) else "hash differs",
                     "bytes_manifest": r.bytes, "bytes_now": len(b), "sha256_manifest": r.sha256, "sha256_now": h})
    listed = set(man.file)
    for p in sorted(RAWDIR.rglob("*")):
        rel = str(p.relative_to(ROOT))
        if p.is_file() and p.suffix in (".csv", ".html", ".txt") and rel not in listed:
            b = p.read_bytes()
            rows.append({"file": rel, "status": "extra (not in manifest)", "bytes_manifest": None,
                         "bytes_now": len(b), "sha256_manifest": None, "sha256_now": hashlib.sha256(b).hexdigest()})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    t = verify()
    t.to_csv(OUTFILE, index=False)
    print(t.status.value_counts().to_string())
    bad = t[t.status != "ok"]
    if len(bad):
        print(bad[["file", "status", "bytes_manifest", "bytes_now"]].to_string(index=False))
        sys.exit(1)
    print("all", len(t), "files match the manifest")

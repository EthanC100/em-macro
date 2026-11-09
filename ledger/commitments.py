"""Salted commitments to private (licensed) values, e.g. an entry at an exchange settlement.

    python -m ledger.commitments verify                      # every commitment named in the public terms
    python -m ledger.commitments verify <commitment hex> ...
    python -m ledger.commitments recommit D003 --supersedes K002
                                                             # a writable private store only (the private-commitments
                                                             # workflow): new salted commitments, then the correction

A plain hash of a settlement can be brute-forced: a price to 0.01 has only ~20,000 plausible values. A commitment
is therefore ``SHA-256(salt || value)``, where ``salt`` is 32 random bytes (``secrets.token_bytes``) generated for
that value alone, and ``value`` is the canonical UTF-8 string ``"<PRODUCT> <YYYY-MM>|<date>|<what>|<number %.10g>"``.
- **Only the commitment is published**, in the field it commits to, e.g. ``settlement 2026-11-06 (private; salted
  commitment <hex>)``. The field is part of the sealed entry, so the commitment is covered by the audit chain.
- **The salt and the value are kept only in the private store** (em-macro-data ``ledger/commitments.jsonl``).
- ``verify`` recomputes each commitment from the private salt and value. Where the store holds the settlement, it
  also checks that the value equals what the ledger derives from it today. It never prints a salt or a value: its
  output may appear in a public workflow log.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import derivs as DV
from . import settlements as ST

ROOT = Path(__file__).resolve().parents[1]
COMMIT_FILE = "ledger/commitments.jsonl"
SALT_BYTES = 32
HEX64 = re.compile(r"salted commitment ([0-9a-f]{64})")


def canonical(product: str, month: str, d: str, what: str, number: float) -> str:
    return f"{product} {month}|{d}|{what}|{number:.10g}"


def commitment(salt: bytes, value: str) -> str:
    return hashlib.sha256(salt + value.encode("utf-8")).hexdigest()


def _path(store: Path) -> Path:
    return store / COMMIT_FILE


def load(store: Path | None) -> list[dict]:
    if not store or not _path(store).exists():
        return []
    return [json.loads(x) for x in _path(store).read_text(encoding="utf-8").splitlines() if x.strip()]


def new(label: str, value: str, store: Path, now: str | None = None) -> str:
    """A new salted commitment to ``value``; the salt and value go to the private store only. Returns the
    commitment (hex), the only part that may be published."""
    ST._guard_write(store)                       # never from a read-only clone (Janus sessions)
    salt = secrets.token_bytes(SALT_BYTES)
    c = commitment(salt, value)
    p = _path(store)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"commitment": c, "label": label, "value": value, "salt": salt.hex(),
                            "created_at": now or datetime.now(timezone.utc).replace(microsecond=0).isoformat()},
                           sort_keys=True) + "\n")
    return c


def verify_one(c: str, store: Path | None, expected_value: str | None = None) -> dict:
    """{"commitment", "label", "ok", "error"}; never the salt or the value."""
    rec = next((r for r in load(store) if r.get("commitment") == c), None)
    if rec is None:
        return {"commitment": c, "label": None, "ok": False, "error": "no private salt for this commitment"}
    if commitment(bytes.fromhex(rec["salt"]), rec["value"]) != c:
        return {"commitment": c, "label": rec.get("label"), "ok": False, "error": "salt and value do not reproduce it"}
    if expected_value is not None and rec["value"] != expected_value:
        return {"commitment": c, "label": rec.get("label"), "ok": False,
                "error": "the committed value differs from the value derived from the private store today"}
    return {"commitment": c, "label": rec.get("label"), "ok": True, "error": None,
            "checked_against_store": expected_value is not None}


def private_values(terms: dict, srows: list[dict]) -> dict[str, str] | None:
    """Canonical values of a private entry, derived from the private store: {field: value}; None without the
    entry settlement."""
    m = DV.PRIVATE_ENTRY.match(terms.get("entry_underlying") or "")
    if not m:
        return {}
    t = DV.resolve_terms(terms, srows)
    if t is None:
        return None
    prod, month, d = terms["product"], terms["contract_month"], m.group(1)
    out = {"entry_underlying": canonical(prod, month, d, "settlement", float(t["entry_underlying"]))}
    if terms["structure"] != "future" and (terms.get("entry_premium") or "").startswith(DV.PRIVATE_PREMIUM_PREFIX):
        out["entry_premium"] = canonical(prod, month, d, "entry_premium", float(t["entry_premium"]))
    return out


def verify_all(root: Path = ROOT, store: Path | None = None) -> dict:
    """Every salted commitment named in the public derivative terms."""
    store = store if store is not None else DV.data_store(root)
    srows = DV.settlements(store)
    results = []
    for did, t in DV.load_terms(root).items():
        derived = private_values(t, srows) or {}
        for field in ("entry_underlying", "entry_premium"):
            m = HEX64.search(t.get(field) or "")
            if m:
                results.append({"decision": did, "field": field, **verify_one(m.group(1), store, derived.get(field))})
    return {"ok": all(r["ok"] for r in results), "n": len(results), "results": results}


def committed_fields(terms: dict, values: dict[str, str], store: Path, did: str, now: str | None = None) -> dict:
    """New field texts carrying salted commitments for each private value (for a correction)."""
    out = {}
    m = DV.PRIVATE_ENTRY.match(terms["entry_underlying"])
    for field, value in values.items():
        c = new(f"{did} {field}", value, store, now)
        if field == "entry_underlying":
            out[field] = f"settlement {m.group(1)} (private; salted commitment {c})"
        else:
            out[field] = f"{DV.PRIVATE_PREMIUM_PREFIX}; salted commitment {c})"
    return out


def recommit(did: str, supersedes: str, root: Path = ROOT, store: Path | None = None, now: str | None = None) -> list[dict]:
    """Replace a private entry's unsalted digests (published in correction ``supersedes``) with salted commitments,
    recorded as a new correction. Needs a writable private store holding the entry settlement."""
    from . import audit as AUD
    store = store if store is not None else DV.data_store(root)
    if store is None:
        raise ValueError("no private store (EM_MACRO_DATA)")
    ST._guard_write(store)
    t = DV.load_terms(root).get(did)
    if not t or not DV.is_private(t):
        raise ValueError(f"{did} has no private entry")
    if HEX64.search(t.get("entry_underlying") or ""):
        raise ValueError(f"{did} already carries salted commitments")
    values = private_values(t, DV.settlements(store))
    if not values:
        raise ValueError(f"{did}: the entry settlement is not in the private store; fetch it first")
    fields = committed_fields(t, values, store, did, now)
    reason = (f"Salted commitments replace the unsalted SHA-256 digests published in {supersedes}'s reason. A "
              "settlement to 0.01 has only about 20,000 plausible values, so those digests can be brute-forced: treat "
              f"them as disclosing the values ({supersedes}'s record stays in the append-only chain unchanged). Each "
              "private value (the entry settlement, and the premium repriced at it) is now committed as SHA-256(salt "
              "|| value) with its own random 32-byte salt, kept only in em-macro-data (ledger/commitments.jsonl); only "
              "the commitment is published, in the field it commits to. `python -m ledger.commitments verify` checks "
              "them with the private salts. The values are unchanged.")
    return AUD.correct_many([("derivative", did, fields)], reason, root / "data/ledger/seals.jsonl", now)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verify")
    v.add_argument("commitments", nargs="*")
    r = sub.add_parser("recommit")
    r.add_argument("decision")
    r.add_argument("--supersedes", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        store = DV.data_store()
        res = ({"results": [verify_one(c, store) for c in a.commitments]} if a.commitments else verify_all())
        res["ok"] = all(x["ok"] for x in res["results"]) and bool(res["results"])
        print(json.dumps(res, indent=1))            # commitments, labels and ok only: no salt, no value
        return 0 if res["ok"] else 1
    recs = recommit(a.decision, a.supersedes)
    print(json.dumps([{"correction_id": x["correction_id"], "id": x["id"], "fields": sorted(x["fields"])} for x in recs]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

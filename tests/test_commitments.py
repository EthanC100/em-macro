"""Salted commitments to private values (ledger/commitments.py). Synthetic prices only."""
import hashlib
import json
from datetime import date

import pytest

from ledger import audit, commitments as CM, derivs as DV
from test_derivs import _k002, _rows, _settle, ledger_root   # noqa: F401  (fixture)


def test_commitment_is_salted_and_resists_brute_force(tmp_path):
    store = tmp_path / "store"
    value = CM.canonical("BRENT", "2027-03", "2026-11-06", "settlement", 91.7)
    c = CM.new("D003 entry_underlying", value, store)
    rec = CM.load(store)[0]
    assert len(bytes.fromhex(rec["salt"])) == 32 and rec["value"] == value
    assert c == hashlib.sha256(bytes.fromhex(rec["salt"]) + value.encode()).hexdigest()
    # hashing every plausible settlement without the salt never finds it
    cands = {hashlib.sha256(CM.canonical("BRENT", "2027-03", "2026-11-06", "settlement", k / 100).encode()).hexdigest()
             for k in range(5_000, 15_000)}
    assert c not in cands
    # two commitments to the same value differ (fresh salt each time)
    assert CM.new("again", value, store) != c
    assert CM.verify_one(c, store)["ok"]
    assert not CM.verify_one("0" * 64, store)["ok"]
    assert not CM.verify_one(c, store, expected_value=value.replace("91.7", "91.8"))["ok"]
    rec["value"] = value.replace("91.7", "91.8")
    (store / CM.COMMIT_FILE).write_text(json.dumps(rec) + "\n")
    assert CM.verify_one(c, store)["error"] == "salt and value do not reproduce it"


def test_recommit_replaces_the_digests_without_breaking_the_chain(ledger_root, tmp_path, monkeypatch):
    did, seals, _ = _k002(ledger_root, monkeypatch)
    store = tmp_path / "em-macro-data"
    with pytest.raises(ValueError, match="not in the private store"):
        CM.recommit(did, "K001", ledger_root, store)
    _settle(store, [("2026-11-06", 91.7), ("2026-11-09", 95.2)])
    before = DV.resolve_terms(DV.load_terms(ledger_root)[did], DV.settlements(store))
    recs = CM.recommit(did, "K001", ledger_root, store)
    assert [r["correction_id"] for r in recs] == ["K002"] and sorted(recs[0]["fields"]) == ["entry_premium",
                                                                                           "entry_underlying"]
    assert audit.verify_seals(seals)["ok"]
    t = DV.load_terms(ledger_root)[did]
    assert DV.is_private(t) and "salted commitment" in t["entry_underlying"] and "salted commitment" in t["entry_premium"]
    after = DV.resolve_terms(t, DV.settlements(store))                # valuation unchanged
    assert {k: after[k] for k in ("entry_underlying", "entry_premium", "risk_per_unit")} == \
           {k: before[k] for k in ("entry_underlying", "entry_premium", "risk_per_unit")}
    v = CM.verify_all(ledger_root, store)
    assert v["ok"] and v["n"] == 2 and all(r["checked_against_store"] for r in v["results"])
    # no salt or private value in any public file
    salts = [r["salt"] for r in CM.load(store)]
    for f in ("data/ledger/derivatives.csv", "data/ledger/decisions.csv", "data/ledger/seals.jsonl"):
        txt = (ledger_root / f).read_text()
        assert "91.7" not in txt and not any(s in txt for s in salts)
    # a second recommit is refused; marking still works from the committed terms
    with pytest.raises(ValueError, match="already carries"):
        CM.recommit(did, "K001", ledger_root, store)
    DV.mark(ledger_root, date(2026, 11, 11), fetch=False)
    mine = [r for r in _rows(ledger_root / DV.PNL) if r["id"] == did]
    assert [r["basis"] for r in mine] == ["entry", "model estimate"]
    # a commitment whose private value no longer matches the store fails verification
    (store / "ledger/futures_settlements.csv").write_text(
        (store / "ledger/futures_settlements.csv").read_text().replace("91.7", "91.6"))
    assert not CM.verify_all(ledger_root, store)["ok"]


def test_read_only_store_cannot_create_commitments(tmp_path):
    from ledger import settlements as ST
    store = tmp_path / "ro"
    store.mkdir()
    (store / ST.READ_ONLY_MARK).write_text("")
    with pytest.raises(ST.ReadOnlyStore):
        CM.new("x", "v", store)


def test_no_unsalted_digest_helper_remains():
    assert not hasattr(DV, "private_entry_digest")

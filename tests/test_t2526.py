"""T25-T26 live shadows (em_macro/t2526_data.py, em_macro/t2526.py), on synthetic data only: no Norgate or Databento
file, no request. Covers the Databento layout and units, the Norgate check (prices, chain, P1) and the exclusion of a
failing market, the history and daily caps, go-live and its refusals, start flat, the missing-data rules of §7,
the drop rule, the three outcomes with Holm at their boundaries, inconclusive-to-decayed, §7.6, and no price in any
public file."""
import json
import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from em_macro import commod_data as CD
from em_macro import t2526 as M
from em_macro import t2526_data as D

DAYS = pd.bdate_range("2023-01-02", "2027-02-26")
NORGATE_END = pd.Timestamp("2026-10-30")
CODES = ["CL", "HO", "RB", "NG", "HG", "ZC", "ZS"]
FACTOR = {"HG": 100.0, "ZC": 1.0}           # Norgate units / Databento units (HG: cents vs USD)


def _cal():
    return CD.BizCal(pd.bdate_range("2021-01-01", DAYS[-1]), "2031-12-31")


def _contracts(code, seed, days=DAYS):
    """Random-walk settlements in Norgate units for every designated contract trading in ``days``; each contract
    trades for 800 days up to its exchange-rule last trade date."""
    rng = np.random.default_rng(seed)
    spot = 300 * (1 + seed) * np.exp(np.cumsum(rng.normal(0, 0.015, len(days))))
    slope = rng.normal(0, 0.05)
    tick = CD.MARKETS[code].tick
    cal = _cal()
    rule = CD.LTD_RULES[CD.MARKETS[code].ltd_rule]
    out = {}
    for y in range(2022, 2030):
        for m in range(1, 13):
            if CD.MONTH_CODES[m - 1] not in CD.MARKETS[code].months:
                continue
            ltd = rule(cal, y, m)
            sel = (days >= ltd - pd.Timedelta(days=800)) & (days <= ltd)
            if not sel.any():
                continue
            tau = (ltd - days[sel]).days / 365
            px = np.round(spot[sel] * np.exp(slope * tau) / tick) * tick
            out[CD.contract_label(code, y, m)] = pd.Series(px, index=days[sel])
    return out


def _write_norgate(root, code, series):
    folder = root / "norgate" / CD.SNAPSHOT / "contracts" / code
    folder.mkdir(parents=True, exist_ok=True)
    for c, s in series.items():
        s = s[s.index <= NORGATE_END]
        if len(s):
            pd.DataFrame({"date": s.index.strftime("%Y-%m-%d"), "close": s.values, "volume": 1}).to_csv(
                folder / f"{c}.csv", index=False)


def _raw(series, factor=1.0, until=None):
    rows = []
    for c, s in series.items():
        if until is not None:
            s = s[s.index <= until]
        rows.append(pd.DataFrame({"date": s.index, "contract": c, "settle": s.values / factor}))
    return pd.concat(rows, ignore_index=True)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """EM_MACRO_DATA with the Databento shadow store (raw and contract files, factors) for CODES."""
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path))
    base = tmp_path / "databento" / "shadows"
    ser = {}
    for k, c in enumerate(CODES):
        ser[c] = _contracts(c, k)
        D.write_raw(c, _raw(ser[c], FACTOR.get(c, 1.0)), base)
        D.write_contracts(c, FACTOR.get(c, 1.0), base)
    (base / "factors.json").write_text(json.dumps({c: {"factor": FACTOR.get(c, 1.0), "passed": True} for c in CODES}))
    return {"root": tmp_path, "base": base, "series": ser}


@pytest.fixture()
def live(store, tmp_path, monkeypatch):
    """A go-live record with M1 = 2026-12 and both shadows on the 7 synthetic markets."""
    out = tmp_path / "results" / "shadows"
    out.mkdir(parents=True)
    pre = out / "prelive.json"
    pre.write_text(json.dumps({"checked_at": "2026-11-20T00:00:00+00:00",
                               "universe_after_check": {"T25": CODES, "T26": CODES}}))
    monkeypatch.setattr(M, "p0_hashes", lambda root=None: {"ok": True, "mismatch": []})
    r = M.golive(date(2026, 11, 20), prelive=pre, out=out / "GO_LIVE.json")
    assert r["ok"]
    return {**store, "out": out, "private": tmp_path / "private"}


def _drop_day(base, code, day):
    """No settlement on ``day`` for any contract of ``code`` but the farthest: the market still trades that day
    (it stays the decision date) but F1 and F2 have no settlement on it (Amendment 4.4: missing)."""
    files = sorted((base / "contracts" / code).glob("*.csv"), key=lambda q: CD.parse_contract(q.stem))
    frames = {q: pd.read_csv(q) for q in files}
    on = [q for q in files if (frames[q]["date"] == day).any()]
    for q in on[:-1]:
        frames[q][frames[q]["date"] != day].to_csv(q, index=False)


def _daily(live, today):
    return M.daily(today, base=live["base"], out=live["out"], private=live["private"])


# ============================================================================ data layer
def test_layout_redirects_and_restores(tmp_path):
    before = (CD.snapshot_dir, CD.norgate_metadata, CD.ASSEMBLY_END_MONTH)
    with D.databento_layout(pd.Period("2027-01", "M"), tmp_path) as b:
        assert CD.snapshot_dir() == b == tmp_path and CD.snapshot_dir("anything") == tmp_path
        assert CD.norgate_metadata() is None and CD.ASSEMBLY_END_MONTH == pd.Period("2027-01", "M")
    assert (CD.snapshot_dir, CD.norgate_metadata, CD.ASSEMBLY_END_MONTH) == before


def test_contract_files_in_norgate_units_read_by_unchanged_marketdata(store):
    base = store["base"]
    s = store["series"]["HG"]
    c = next(iter(s))
    f = pd.read_csv(base / "contracts" / "HG" / f"{c}.csv")
    assert list(f.columns) == ["date", "close", "volume"]
    assert np.allclose(f["close"].values, s[c].values)                      # raw / 100 x 100
    raw = D.read_raw("HG", base)
    assert np.allclose(raw[raw["contract"] == c]["settle"].values * 100, s[c].values)
    with D.databento_layout(pd.Period("2027-02", "M"), base):
        md = CD.MarketData("HG")
        assert md.latest == DAYS[-1]
        assert (md.contracts["ltd_source"].isin(["exchange rule", "norgate final settlement"])).all()
        assert (md.contracts["fnd_source"] != "norgate").all()             # exchange rules, not Norgate metadata
        assert md.rolls.index[-1] == pd.Period("2027-02", "M")


def test_write_raw_deduplicates(tmp_path):
    df = pd.DataFrame({"date": pd.to_datetime(["2026-01-02", "2026-01-05"]), "contract": "CL-2026G",
                       "settle": [1.0, 2.0]})
    assert D.write_raw("CL", df, tmp_path) == 2
    df2 = pd.DataFrame({"date": pd.to_datetime(["2026-01-05", "2026-01-06"]), "contract": "CL-2026G",
                        "settle": [2.5, 3.0]})
    assert D.write_raw("CL", df2, tmp_path) == 1
    r = D.read_raw("CL", tmp_path)
    assert len(r) == 3 and r.loc[r["date"] == "2026-01-05", "settle"].item() == 2.5


def test_compare_prices_factor_and_share():
    idx = pd.bdate_range("2024-01-01", periods=200)
    n = pd.DataFrame({"HG-2024N": np.round(np.linspace(380, 420, 200) / 0.05) * 0.05})
    n.index = idx
    raw = pd.DataFrame({"date": idx, "contract": "HG-2024N", "settle": n["HG-2024N"].values / 100})
    r = D.compare_prices("HG", n, raw)
    assert r["factor"] == 100.0 and r["share"] == 1.0 and r["common_days"] == 200
    raw.loc[:2, "settle"] += 0.002                                           # 0.2 cents = 4 ticks, 3 days of 200
    r = D.compare_prices("HG", n, raw)
    assert r["share"] == pytest.approx(197 / 200)
    assert D.compare_prices("HG", n, raw.iloc[0:0])["factor"] is None


def test_check_excludes_failing_market_counts_only(store, monkeypatch, tmp_path):
    root, base = store["root"], store["base"]
    for c in ("CL", "HG", "NG"):
        _write_norgate(root, c, store["series"][c])
    # NG: Databento differs by 2 ticks on 5% of days -> below 99% within one tick
    raw = D.read_raw("NG", base)
    bad = raw.sample(frac=0.05, random_state=0).index
    raw.loc[bad, "settle"] += 2 * CD.MARKETS["NG"].tick
    (base / "raw" / "NG.csv").unlink()
    D.write_raw("NG", raw, base)
    monkeypatch.setattr(D, "universes", lambda: {"T25": ["CL", "HG", "NG"], "T26": ["CL", "HG", "NG"]})
    monkeypatch.setattr(D, "PRELIVE", tmp_path / "prelive.json")
    s = D.check(["CL", "HG", "NG"], base, log=lambda *_: None)
    m = s["markets"]
    assert m["CL"]["passed"] and m["HG"]["passed"] and not m["NG"]["passed"]
    assert m["HG"]["prices"]["factor"] == 100.0 and m["CL"]["chain"]["equal"] and m["CL"]["chain"]["months"] > 40
    assert "99%" in m["NG"]["reason"]
    assert not (base / "contracts" / "NG").exists() and (base / "contracts" / "HG").is_dir()
    assert s["universe_after_check"] == {"T25": ["CL", "HG"], "T26": ["CL", "HG"]}
    assert json.loads((base / "factors.json").read_text())["NG"]["passed"] is False
    # the committed file holds counts, shares and factors only: no settlement value
    txt = (tmp_path / "prelive.json").read_text()
    vals = set(np.round(raw["settle"].values, 3))
    nums = {round(float(x), 3) for x in __import__("re").findall(r"-?\d+\.\d+", txt)}
    assert not (nums & vals - {1.0, 0.99, 100.0})


def test_p1_counts_from_the_stored_history(store):
    r = D.p1("CL", D.read_raw("CL", store["base"]))
    assert r["qualifies_T25"] and r["qualifies_T26"] and r["min_share_F1"] == 1.0
    raw = D.read_raw("CL", store["base"])
    f1 = "CL-2027G"                                                         # the December 2026 F1
    thin = raw[~((raw["contract"] == f1) & (raw["date"] >= "2026-09-01") & (raw["date"] <= "2026-10-15"))]
    r = D.p1("CL", thin)
    assert not r["qualifies_T25"] and not r["qualifies_T26"]


def test_compare_chains_reports_differing_months(store):
    with D.databento_layout(pd.Period("2026-10", "M"), store["base"]):
        a = CD.MarketData("CL")
        a.rolls
        b = CD.MarketData("CL")
        b.rolls
    assert D.compare_chains(a, b, pd.Period("2023-02", "M"), pd.Period("2026-10", "M"))["equal"]
    b.rolls.loc[pd.Period("2024-05", "M"), "F1"] = "CL-2099F"
    r = D.compare_chains(a, b, pd.Period("2023-02", "M"), pd.Period("2026-10", "M"))
    assert not r["equal"] and r["differing_months"] == ["2024-05"]


class _FakeClient:
    def __init__(self, cost, end="2026-11-20T00:00:00Z"):
        self.cost, self.end = cost, end
        self.downloads = 0
        fake = self

        class Meta:
            def get_dataset_range(self, dataset):
                return {"end": fake.end}

            def get_cost(self, **kw):
                return fake.cost

        class Sym:
            def resolve(self, **kw):
                return {"result": {s: [{"s": "1"}] for s in kw["symbols"] if len(s) == 4}, "not_found": []}

        self.metadata, self.symbology = Meta(), Sym()


def _rows(r):
    """A small fake download: one settlement per contract on the request's first day."""
    d = pd.Timestamp(r["kw"]["start"][:10])
    return pd.DataFrame({"date": d, "contract": sorted(r["map"].values()), "settle": 1.0})


@pytest.fixture()
def no_prior_spend(monkeypatch):
    monkeypatch.setattr(D, "UNLOGGED_SPEND", [])


def test_history_quotes_first_and_refuses_above_20(tmp_path, monkeypatch, no_prior_spend):
    calls = []
    monkeypatch.setattr(D, "_download", lambda c, r: calls.append(r) or _rows(r))
    # 2 markets x 4 calendar years (2023 .. 2026) = 8 requests
    r = D.history(_FakeClient(2.6), ["CL", "NG"], date(2026, 11, 20), tmp_path, log=lambda *_: None)
    assert r["refused"] and r["requests"] == 8 and r["quote_usd"] == pytest.approx(20.8) and not calls
    assert not (tmp_path / D.HISTORY_LEDGER).exists()
    r = D.history(_FakeClient(0.4), ["CL", "NG"], date(2026, 11, 20), tmp_path, log=lambda *_: None)
    assert not r["refused"] and len(calls) == 8 and not r["failed"]
    assert sorted(k["kw"]["start"][:10] for k in calls) == sorted(["2023-01-01", "2024-01-01", "2025-01-01",
                                                                    "2026-01-01"] * 2)
    assert all(s[-1].isdigit() and len(s) == 4 for k in calls for s in k["kw"]["symbols"])   # one-digit year
    led = D.history_ledger(tmp_path)
    assert sum(x["status"] == "sent" for x in led) == 8 and sum(x["status"] == "stored" for x in led) == 8
    assert D.history_spent(tmp_path) == pytest.approx(3.2)
    # a rerun pays for nothing: every piece is stored
    calls.clear()
    r = D.history(_FakeClient(0.4), ["CL", "NG"], date(2026, 11, 20), tmp_path, log=lambda *_: None)
    assert r["requests"] == 0 and not calls


def test_history_skips_markets_stored_whole_and_counts_earlier_spend(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(D, "_download", lambda c, r: calls.append(r) or _rows(r))
    monkeypatch.setattr(D, "UNLOGGED_SPEND", [{"run": "earlier", "usd": 18.5}])
    # CL stored whole by an earlier run (raw file, no ledger line): skipped
    D.write_raw("CL", pd.DataFrame({"date": pd.to_datetime(["2023-01-03"]), "contract": "CL-2023G", "settle": [1.0]}),
                tmp_path)
    r = D.history(_FakeClient(0.4), ["CL", "NG"], date(2026, 11, 20), tmp_path, log=lambda *_: None)
    assert r["refused"] and r["spent_before_usd"] == 18.5 and r["quote_usd"] == pytest.approx(1.6) and not calls
    monkeypatch.setattr(D, "UNLOGGED_SPEND", [{"run": "earlier", "usd": 18.0}])
    r = D.history(_FakeClient(0.4), ["CL", "NG"], date(2026, 11, 20), tmp_path, log=lambda *_: None)
    assert not r["refused"] and r["markets"] == 1 and len(calls) == 4
    assert all(s.startswith("NG") for k in calls for s in k["kw"]["symbols"])
    assert r["spent_after_usd"] == pytest.approx(19.6)


def test_history_interrupted_piece_counts_and_is_fetched_again(tmp_path, monkeypatch, no_prior_spend):
    stored_msgs = []
    fail = {"n": 0}

    def dl(c, r):
        if r["kw"]["start"].startswith("2024") and "NG" in r["kw"]["symbols"][0] and fail["n"] < 3:
            fail["n"] += 1
            raise ConnectionError("reset")
        return _rows(r)
    monkeypatch.setattr(D, "_download", dl)
    monkeypatch.setattr(D, "_retry", lambda fn, tries=4, wait=0, log=None, what="": _retry_fast(fn, tries))
    r = D.history(_FakeClient(0.5), ["CL", "NG"], date(2026, 11, 20), tmp_path, log=lambda *_: None,
                  on_stored=stored_msgs.append)
    # NG 2024 failed on all 3 attempts: each attempt was sent and counts; the other 7 pieces were stored at once
    assert len(r["failed"]) == 1 and len(stored_msgs) == 7 and "NG 2024" not in " ".join(stored_msgs)
    assert D.history_spent(tmp_path) == pytest.approx(0.5 * (7 + 3))
    # the rerun fetches only NG 2024, and the cap counts everything paid so far
    r = D.history(_FakeClient(0.5), ["CL", "NG"], date(2026, 11, 20), tmp_path, log=lambda *_: None,
                  on_stored=stored_msgs.append)
    assert r["requests"] == 1 and r["spent_before_usd"] == pytest.approx(5.0) and not r["failed"]
    assert stored_msgs[-1].endswith("NG 2024")


def _retry_fast(fn, tries):
    for k in range(tries):
        try:
            return fn()
        except Exception:
            if k == tries - 1:
                raise


def test_history_stops_at_the_cap_mid_run(tmp_path, monkeypatch, no_prior_spend):
    monkeypatch.setattr(D, "_download", lambda c, r: (_ for _ in ()).throw(ConnectionError("reset")))
    monkeypatch.setattr(D, "_retry", lambda fn, tries=4, wait=0, log=None, what="": _retry_fast(fn, tries))
    r = D.history(_FakeClient(2.0), ["CL", "NG"], date(2026, 11, 20), tmp_path, log=lambda *_: None, workers=1)
    # quoted 16 <= 20, but every retry is a new paid request: stopped before the spend passes US$20
    assert r["failed"] and D.history_spent(tmp_path) <= 20.0 + 1e-9
    assert any("would take the one-off spend above" in e for e in r["failed"])


def test_history_chunks():
    from datetime import datetime, timezone
    ch = D.history_chunks(datetime(2026, 11, 6, 18, 33, tzinfo=timezone.utc))
    assert [c[0] for c in ch] == ["2023", "2024", "2025", "2026"] and ch[0][1] == date(2023, 1, 1)
    assert ch[-1][2] == datetime(2026, 11, 6, 18, 33, tzinfo=timezone.utc)


def test_unlogged_spend_is_recorded():
    assert D.UNLOGGED_SPEND and D.UNLOGGED_SPEND[0]["usd"] > 0
    assert D.UNLOGGED_SPEND[0]["markets_stored"] == ["CL", "RB", "HO", "NG", "HG", "GC", "SI", "PL"]


def test_update_under_the_shared_daily_cap(store, monkeypatch):
    from ledger import settlements as ST
    base = store["base"]
    monkeypatch.setattr(D, "_download", lambda c, r: pd.DataFrame(columns=["date", "contract", "settle"]))
    ST._log_spend(store["root"], {"utc_date": "2027-02-27", "downloaded": True, "quote_usd": 0.75})
    r = D.update(_FakeClient(0.1, "2027-03-02T00:00:00Z"), ["CL", "HO", "RB"], date(2027, 2, 27), base, store["root"])
    assert "refused" in r["log"][0]
    r = D.update(_FakeClient(0.01, "2027-03-02T00:00:00Z"), ["CL"], date(2027, 2, 27), base, store["root"])
    assert "quote" in r["log"][0] and ST.spent_today(store["root"], date(2027, 2, 27)) == pytest.approx(0.76)
    (base / ST.READ_ONLY_MARK).write_text("")
    assert D.update(_FakeClient(0.01, "2027-03-02T00:00:00Z"), ["CL"], date(2027, 2, 27), base, store["root"])["log"] == \
        ["read-only store: nothing fetched"]


# ============================================================================ go-live
def test_golive_refusals_and_record(store, tmp_path, monkeypatch):
    out = tmp_path / "g" / "GO_LIVE.json"
    pre = tmp_path / "prelive.json"
    assert "pre-live" in M.golive(date(2026, 11, 20), prelive=pre, out=out)["reason"]
    pre.write_text(json.dumps({"universe_after_check": {"T25": CODES[:5], "T26": CODES}}))
    monkeypatch.setattr(M, "p0_hashes", lambda root=None: {"ok": False, "mismatch": ["em_macro/t2022.py"]})
    assert "P0" in M.golive(date(2026, 11, 20), prelive=pre, out=out)["reason"]
    monkeypatch.setattr(M, "p0_hashes", lambda root=None: {"ok": True, "mismatch": []})
    assert "fewer than 6" in M.golive(date(2026, 11, 20), prelive=pre, out=out)["reason"]
    pre.write_text(json.dumps({"universe_after_check": {"T25": CODES, "T26": CODES}}))
    assert "5 May 2027" in M.golive(date(2027, 5, 5), prelive=pre, out=out)["reason"]
    assert not out.exists()
    r = M.golive(date(2026, 11, 20), prelive=pre, out=out)
    assert r["ok"] and r["M1"] == "2026-12" and r["confirmed"] is False
    assert r["first_evaluation"] == {"months": "2026-12..2031-11", "date": "2031-12-15"}
    assert r["second_evaluation"]["months"] == "2026-12..2034-11" and r["second_evaluation"]["date"] == "2034-12-15"
    assert r["N"] == {"T25": 7, "T26": 7}
    assert r["sr_pred"]["T25"] == round(0.4346 * math.sqrt(7 / 20), 4)
    assert M.golive(date(2026, 11, 21), prelive=pre, out=out)["reason"] == "already live"


def test_p0_hashes_match_the_repository():
    assert M.p0_hashes()["ok"]


def test_first_rebalance_month_and_dates():
    assert M.first_rebalance_month(date(2026, 12, 3)) == pd.Period("2026-12", "M")
    assert M.first_rebalance_month(date(2026, 12, 4)) == pd.Period("2027-01", "M")
    assert M.evaluation_dates(pd.Period("2027-01", "M")) == (date(2032, 1, 15), date(2035, 1, 15))


# ============================================================================ live operation
def test_start_flat_confirm_and_public_files(live):
    assert _daily(live, date(2026, 11, 30))["reason"].startswith("first live month")
    r = _daily(live, date(2027, 2, 26))
    assert r["live"], r
    g = json.loads((live["out"] / "GO_LIVE.json").read_text())
    assert g["confirmed"] and g["M1"] == "2026-12" and g["P3_P4"]["T25"]["P4_active"] >= 6
    for k in M.TRIALS:
        st = json.loads((live["out"] / k / "status.json").read_text())
        assert st["months_live"] == 3 and list(st["rebalances"]) == ["2026-12", "2027-01", "2027-02"]
        pos = pd.read_csv(live["out"] / k / "positions.csv")
        assert pos["month"].min() == "2026-12"                               # nothing before M1
        assert list(pos.columns) == ["month", "market", "contract", "target_weight", "held_weight"]
        idx = pd.read_csv(live["out"] / k / "index.csv")
        assert idx["date"].min() >= "2026-12-03" and idx["index_net_decisive"].iloc[0] < 100   # entry costs
        mon = pd.read_csv(live["out"] / k / "monthly.csv")
        assert list(mon["month"]) == ["2026-12", "2027-01", "2027-02"]
        assert (mon["cost_1x_%"] >= 0).all()
        # private files exist only in the private store
        assert (live["private"] / k / "per_market_daily_gross.csv").exists()
    run = M.run_trial("T25", g, date(2027, 2, 26), live["base"], live["out"])
    gross = run["sl"].per_market_gross
    assert (gross[gross.index < pd.Timestamp("2026-12-03")] == 0).all().all()   # flat before M1's execution
    assert set(run["sl"].held.index) == {pd.Period(m, "M") for m in ("2026-12", "2027-01", "2027-02")}


def test_no_price_in_any_public_file(live):
    _daily(live, date(2027, 2, 26))
    prices = set()
    for c, ser in live["series"].items():
        for s in ser.values():
            prices |= set(np.round(s.values, 2)) | set(np.round(s.values / FACTOR.get(c, 1.0), 2))
    for k in M.TRIALS:
        for f in ("positions.csv", "monthly.csv"):
            df = pd.read_csv(live["out"] / k / f)
            num = df.select_dtypes("number")
            assert (num.abs() < 100).all().all()                          # weights and % only
        idx = pd.read_csv(live["out"] / k / "index.csv")
        assert set(idx.columns) == {"date", "index_net_decisive"}
        txt = (live["out"] / k / "status.json").read_text()
        nums = {round(float(x), 2) for x in __import__("re").findall(r"\d+\.\d+", txt)}
        assert not {n for n in nums if n > 1} & prices
    assert not any(p.suffix == ".csv" and "gross" in p.name for p in live["out"].rglob("*"))


def test_ledger_shadows_section(live):
    from ledger import build as B
    before = B.build_shadows(live["root"])
    assert before["go_live"]["M1"] == "2026-12" and not before["go_live"]["confirmed"]
    assert [i["live"] for i in before["items"]] == [False, False]
    _daily(live, date(2027, 2, 26))
    sh = B.build_shadows(live["root"])
    assert sh["go_live"]["confirmed"] and sh["label"].startswith("zero size, paper")
    for it in sh["items"]:
        assert it["live"] and it["months_live"] == 3 and it["last_rebalance"] == "2027-02"
        assert it["series"][0][0] >= "2026-12-03" and it["positions"]
        assert all(set(p) == {"market", "contract", "held_weight", "target_weight", "direction"} for p in it["positions"])
        assert all((p["direction"] == "long") == (p["held_weight"] > 0) for p in it["positions"])


def test_rebalance_waits_until_the_10th_then_freezes_missing(live):
    base = live["base"]
    # ZS: F1 and F2 have no settlement on the December decision date (2 Dec 2026)
    _drop_day(base, "ZS", "2026-12-02")
    r = _daily(live, date(2026, 12, 9))
    assert not r["live"]
    g = json.loads((live["out"] / "GO_LIVE.json").read_text())
    assert not g["confirmed"] and g["M1"] == "2026-12"
    # after the 10th: computed, ZS missing; with 6 markets left the sleeves still go live
    r = _daily(live, date(2026, 12, 11))
    assert r["live"]
    st = json.loads((live["out"] / "T25" / "status.json").read_text())
    assert st["rebalances"]["2026-12"]["missing"] == ["ZS"] and st["active_markets"]["2026-12"] == 6
    pos = pd.read_csv(live["out"] / "T25" / "positions.csv")
    assert "ZS" not in set(pos[pos["month"] == "2026-12"]["market"])
    # the settlement arrives later: the month stays as computed (frozen), ZS still missing for 2026-12
    D.write_contracts("ZS", 1.0, base)
    _daily(live, date(2027, 2, 26))
    st = json.loads((live["out"] / "T25" / "status.json").read_text())
    assert st["rebalances"]["2026-12"]["missing"] == ["ZS"] and st["rebalances"]["2027-01"]["missing"] == []
    pos = pd.read_csv(live["out"] / "T25" / "positions.csv")
    assert "ZS" not in set(pos[pos["month"] == "2026-12"]["market"])


def test_fewer_than_6_active_moves_go_live(live):
    base = live["base"]
    for c in ("ZS", "ZC"):
        _drop_day(base, c, "2026-12-02")
    r = _daily(live, date(2026, 12, 11))
    assert not r["live"] and "moved from 2026-12" in r["reason"]
    g = json.loads((live["out"] / "GO_LIVE.json").read_text())
    assert g["M1"] == "2027-01" and g["first_evaluation"]["date"] == "2032-01-15"
    assert g["moved"][0]["P3_P4"]["T25"]["P4_active"] == 5
    r = _daily(live, date(2027, 2, 26))
    assert r["live"]
    pos = pd.read_csv(live["out"] / "T25" / "positions.csv")
    assert pos["month"].min() == "2027-01"


def test_t21_holds_nothing_in_a_month_with_fewer_than_6(live):
    _daily(live, date(2027, 2, 26))
    g = json.loads((live["out"] / "GO_LIVE.json").read_text())
    st = json.loads((live["out"] / "T25" / "status.json").read_text())
    st["rebalances"]["2027-01"]["missing"] = ["ZS", "ZC"]                  # a frozen month with 5 markets
    (live["out"] / "T25" / "status.json").write_text(json.dumps(st))
    run = M.run_trial("T25", g, date(2027, 2, 26), live["base"], live["out"])
    assert (run["W"].loc[pd.Period("2027-01", "M")] == 0).all()
    assert len(M.active_markets(run, pd.Period("2027-02", "M"))) == 7
    assert (run["W"].loc[pd.Period("2027-02", "M")] != 0).sum() >= 6         # the middle rank weighs 0


def test_drop_after_20_days_without_settlement(live):
    base = live["base"]
    _daily(live, date(2027, 1, 5))
    g = json.loads((live["out"] / "GO_LIVE.json").read_text())
    run = M.run_trial("T26", g, date(2027, 1, 5), base, live["out"])
    held = run["sl"].held.loc[pd.Period("2027-01", "M")]
    c = held[held != 0].index[0]
    f1 = run["mks"][c].rolls.at[pd.Period("2027-01", "M"), "F1"]
    # every settlement of the market stops after 2027-01-08 (delisted, or an outage that never ends)
    for q in (base / "contracts" / c).glob("*.csv"):
        df = pd.read_csv(q)
        df[df["date"] <= "2027-01-08"].to_csv(q, index=False)
    _daily(live, date(2027, 2, 26))
    st = json.loads((live["out"] / "T26" / "status.json").read_text())
    d = st["dropped"][c]
    # the 21st trading day after 8 Jan is after 3 Feb: dropped from the March rebalance, not yet computed
    assert d["last_settlement"] == "2027-01-08" and d["from_month"] == "2027-03" and d["contract"] == f1
    assert st["last_rebalance"] == "2027-02" and st["rebalances"]["2027-02"]["missing"] == [c]
    # the drop applied from a computed month: closed in full, 3x the one-way cost at its last settlement
    st["dropped"][c]["from_month"] = "2027-02"
    (live["out"] / "T26" / "status.json").write_text(json.dumps(st))
    run2 = M.run_trial("T26", g, date(2027, 2, 26), base, live["out"])
    sl = run2["sl"]
    assert sl.held.at[pd.Period("2027-02", "M"), c] == 0.0
    ex = sl.trades[(sl.trades["market"] == c) & (sl.trades["kind"] == "exit (dropped, §7.4)")].iloc[0]
    w_jan = sl.held.at[pd.Period("2027-01", "M"), c]
    assert ex["w_old"] == w_jan and ex["contract_old"] == f1
    cost = 3 * abs(w_jan) * sl.c_raw(run2["mks"][c], f1, pd.Timestamp("2027-01-08"))
    assert cost > 0 and sl.daily_cost1[ex["date"]] >= cost - 1e-15
    assert ex["date"] >= pd.Timestamp("2027-02-03")


# ============================================================================ evaluation
def test_decay_test_formula():
    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(0.01, 0.03, 60))
    d = M.decay_test(r, 0.3)
    s = r.std(ddof=1)
    m0 = 0.3 / math.sqrt(12) * s
    from em_macro import t2022 as T
    assert d["m0"] == pytest.approx(m0) and d["t_d"] == pytest.approx(T.nw_tstat(r - m0)[1])
    assert d["p_d"] == pytest.approx(0.5 * (1 + math.erf(d["t_d"] / math.sqrt(2))))


def _ev(n=60, mean=0.01, comb_better=True):
    rng = np.random.default_rng(3)
    r = pd.Series(rng.normal(mean, 0.03, n))
    v11 = pd.Series(rng.normal(0.006, 0.02, n))
    comb = v11 + (0.25 * r if comb_better else -0.5 * r.abs())
    return {"r": r, "comb": comb, "v11": v11, "sr_pred": 0.3}


@pytest.mark.parametrize("p,second,expect", [
    ({"T25": 0.024, "T26": 0.04}, False, {"T25": "decayed", "T26": "decayed"}),       # 0.048, 0.048
    ({"T25": 0.026, "T26": 0.03}, False, {"T25": "confirmed", "T26": "confirmed"}),   # 0.052, 0.052
    ({"T25": 0.01, "T26": 0.06}, False, {"T25": "decayed", "T26": "confirmed"}),      # 0.02, 0.06
    ({"T25": 0.049}, False, {"T25": "decayed"}),                                      # one sleeve: no adjustment
    ({"T25": 0.05}, False, {"T25": "confirmed"}),
])
def test_holm_boundaries(monkeypatch, p, second, expect):
    real = M.decay_test
    monkeypatch.setattr(M, "decay_test", lambda r, s: {**real(r, s), "p_d": p[_key(r)]})
    ev = {k: {**_ev(), "r": _tag(_ev()["r"], k)} for k in p}
    out = M.outcomes(ev, second)
    assert {k: v["outcome"] for k, v in out.items()} == expect


def _tag(r, k):
    r = r.copy()
    r.name = k
    return r


def _key(r):
    return r.name


def test_inconclusive_then_decayed_at_the_second_evaluation(monkeypatch):
    real = M.decay_test
    monkeypatch.setattr(M, "decay_test", lambda r, s: {**real(r, s), "p_d": 0.5})
    ev = {"T25": _ev(comb_better=False)}                                       # fails drawdown/Sharpe margins
    assert M.outcomes(ev, False)["T25"]["outcome"] == "inconclusive"
    o = M.outcomes(ev, True)["T25"]
    assert o["outcome"] == "decayed" and o["inconclusive_counted_as_decayed"]
    neg = {"T25": {**_ev(mean=-0.02), "comb": _ev()["v11"] * 1.0}}           # m <= 0 -> not confirmed
    monkeypatch.setattr(M, "decay_test", lambda r, s: {**real(r, s), "p_d": 0.2})
    assert M.outcomes(neg, False)["T25"]["outcome"] == "inconclusive"


def test_confirmed_needs_all_three_point_conditions(monkeypatch):
    real = M.decay_test
    monkeypatch.setattr(M, "decay_test", lambda r, s: {**real(r, s), "p_d": 0.5})
    e = _ev()
    assert M.outcomes({"T25": e}, False)["T25"]["outcome"] == "confirmed"
    # Sharpe 0.06 lower: fails the -0.05 margin
    sr_v = M.sharpe(e["v11"])
    target = sr_v - 0.06
    comb = (e["v11"] - e["v11"].mean()) + target / math.sqrt(12) * e["v11"].std(ddof=1)
    o = M.outcomes({"T25": {**e, "comb": comb}}, False)["T25"]
    assert o["delta_sr"] == pytest.approx(-0.06) and o["outcome"] == "inconclusive"


def test_evaluable_rule():
    months = pd.period_range("2026-12", periods=60, freq="M")
    frozen = {str(m): {"missing": []} for m in months}
    active = {str(m): 7 for m in months}
    assert M.evaluable(frozen, active, months, 7)["evaluable"]
    a = {**active, **{str(m): 5 for m in months[:7]}}                          # 53 of 60 with >= 6
    assert not M.evaluable(frozen, a, months, 7)["evaluable"]
    a[str(months[6])] = 6                                                       # 54 of 60
    assert M.evaluable(frozen, a, months, 7)["evaluable"]
    gap = {k: v for k, v in frozen.items() if k not in ("2027-03", "2027-04", "2027-05", "2027-06")}
    e = M.evaluable(gap, active, months, 7)
    assert e["longest_interruption"] == 4 and not e["evaluable"]
    gone = ("2027-03", "2027-04", "2027-05")
    allmiss = {**frozen, **{k: {"missing": list("abcdefg")} for k in gone}}
    e = M.evaluable(allmiss, {**active, **{k: 0 for k in gone}}, months, 7)
    assert e["longest_interruption"] == 3 and e["evaluable"]                  # 57 good months, 3-month gap

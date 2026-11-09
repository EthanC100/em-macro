"""ledger/settlements.py: Databento final settlements into the private store, quoted first, US$1 daily cap."""
import json
from datetime import date, datetime, timezone

import pandas as pd
import pytest

from ledger import settlements as ST


class FakeClient:
    """Stands in for databento.Historical: symbology, metadata (cost, range) and timeseries."""

    def __init__(self, rows, cost=0.0001, end="2026-11-10T06:00:00.000000000Z", known=None):
        self.rows, self.cost, self.end, self.known, self.calls = rows, cost, end, known, []
        outer = self

        class Sym:
            def resolve(self, **kw):
                outer.calls.append(("resolve", kw))
                ok = [s for s in kw["symbols"] if outer.known is None or s in outer.known]
                return {"result": {s: [{"s": "1"}] for s in ok}, "not_found": [s for s in kw["symbols"] if s not in ok]}

        class Meta:
            def get_cost(self, **kw):
                outer.calls.append(("cost", kw))
                return outer.cost

            def get_dataset_range(self, **kw):
                return {"end": outer.end, "schema": {"statistics": {"end": outer.end}}}

        class TS:
            def get_range(self, **kw):
                outer.calls.append(("get_range", kw))

                class R:
                    def to_df(self, map_symbols=True):
                        df = pd.DataFrame(outer.rows)
                        return df[df["symbol"].isin(kw["symbols"])].set_index("ts_recv")
                return R()

        self.symbology, self.metadata, self.timeseries = Sym(), Meta(), TS()


def _stat(sym, day, price, final=True, recv_h=23):
    return {"ts_recv": pd.Timestamp(f"{day} {recv_h}:00", tz="UTC"), "ts_ref": pd.Timestamp(day, tz="UTC"),
            "symbol": sym, "stat_type": 3, "stat_flags": 3 if final else 2, "price": price}


ROWS = [_stat("BZH7", "2026-11-06", 93.10, final=False, recv_h=19), _stat("BZH7", "2026-11-06", 93.25),
        _stat("BZH7", "2026-11-09", 95.5), _stat("BZH7", "2026-11-09", 95.0, final=False, recv_h=19),
        {**_stat("BZH7", "2026-11-09", 1.0), "stat_type": 4}]                   # not a settlement


def test_final_settlement_only_and_private_store(tmp_path):
    c = FakeClient(ROWS)
    res = ST.fetch({("BRENT", "2027-03"): date(2026, 11, 6)}, date(2026, 11, 10), tmp_path, c=c)
    rows = ST.read(tmp_path)
    assert [(r["date"], r["settle"]) for r in rows] == [("2026-11-06", "93.25"), ("2026-11-09", "95.5")]
    assert rows[0]["source"].startswith("Databento GLBX.MDP3 statistics, final settlement")
    assert res["stored"] == 2 and not res["refused"]
    kinds = [k for k, _ in c.calls]
    assert kinds.index("cost") < kinds.index("get_range")          # quoted before every request
    spend = [json.loads(x) for x in (tmp_path / ST.SPEND_FILE).read_text().splitlines()]
    assert spend[-1]["downloaded"] and spend[-1]["quote_usd"] == 0.0001
    # the next fetch asks again for the last REFETCH_DAYS days (here back to the first date needed)
    res = ST.fetch({("BRENT", "2027-03"): date(2026, 11, 6)}, date(2026, 11, 10), tmp_path, c=c)
    last_get = [kw for k, kw in c.calls if k == "get_range"][-1]
    assert last_get["start"].startswith("2026-11-06") and res["stored"] == 0      # nothing new, nothing duplicated
    assert len(ST.read(tmp_path)) == 2


def test_late_final_settlement_is_still_fetched(tmp_path):
    """6 Nov's final arrived on Sunday 8 Nov (and Databento had withdrawn the day meanwhile): a run that already
    stored a later day must still pick it up."""
    later = [_stat("BZH7", "2026-11-09", 95.5)]
    ST.fetch({("BRENT", "2027-03"): date(2026, 11, 6)}, date(2026, 11, 10), tmp_path, c=FakeClient(later))
    assert [r["date"] for r in ST.read(tmp_path)] == ["2026-11-09"]
    c = FakeClient(later + [_stat("BZH7", "2026-11-06", 93.30)], end="2026-11-11T06:00:00.000000000Z")
    res = ST.fetch({("BRENT", "2027-03"): date(2026, 11, 6)}, date(2026, 11, 11), tmp_path, c=c)
    assert res["stored"] == 1 and [r["date"] for r in ST.read(tmp_path)] == ["2026-11-06", "2026-11-09"]
    # long after: the window is the last REFETCH_DAYS days before the newest stored settlement, not the whole history
    c2 = FakeClient(later + [_stat("BZH7", "2026-11-20", 96.0)], end="2026-11-21T06:00:00.000000000Z")
    ST.fetch({("BRENT", "2027-03"): date(2026, 11, 6)}, date(2026, 11, 21), tmp_path, c=c2)
    c3 = FakeClient([], end="2026-11-22T06:00:00.000000000Z")
    ST.fetch({("BRENT", "2027-03"): date(2026, 11, 6)}, date(2026, 11, 22), tmp_path, c=c3)
    assert [kw for k, kw in c3.calls if k == "get_range"][-1]["start"].startswith("2026-11-14")


def test_daily_cap_refuses_and_is_shared(tmp_path):
    c = FakeClient(ROWS, cost=0.6)
    a = ST.fetch({("BRENT", "2027-03"): date(2026, 11, 6)}, date(2026, 11, 10), tmp_path, c=c, purpose="me")
    assert a["stored"] == 2
    b = ST.fetch({("WTI", "2027-01"): date(2026, 11, 6)}, date(2026, 11, 10), tmp_path,
                 c=FakeClient([_stat("CLF7", "2026-11-06", 87.0)], cost=0.6), purpose="janus")
    assert b["refused"] and "above US$1.00" in b["log"][-1]
    assert ST.read(tmp_path) and all(r["product"] == "BRENT" for r in ST.read(tmp_path))
    assert ST.spent_today(tmp_path, date(2026, 11, 10)) == pytest.approx(0.6)
    assert ST.spent_today(tmp_path, date(2026, 11, 11)) == 0.0     # a new UTC day
    # a single request above the cap is refused outright
    big = FakeClient([], cost=1.5)
    r = ST.fetch({("WTI", "2027-01"): date(2026, 11, 6)}, date(2026, 11, 11), tmp_path, c=big)
    assert r["refused"] and not any(k == "get_range" for k, _ in big.calls)


def test_no_store_fetches_nothing():
    c = FakeClient(ROWS)
    res = ST.fetch({("BRENT", "2027-03"): date(2026, 11, 6)}, date(2026, 11, 10), store=None, c=c)
    assert res["stored"] == 0 and "no private store" in res["log"][0] and c.calls == []


def test_two_digit_year_symbols_are_resolved(tmp_path):
    c = FakeClient([_stat("NGF27", "2026-11-06", 3.9)], known={"NGF27"})
    res = ST.fetch({("NATGAS", "2027-01"): date(2026, 11, 6)}, date(2026, 11, 10), tmp_path, c=c)
    assert res["stored"] == 1 and ST.read(tmp_path)[0]["contract_month"] == "2027-01"
    assert "NGF27" in [kw for k, kw in c.calls if k == "get_range"][0]["symbols"]


def test_calendar():
    assert ST.contract_code("BRENT", "2027-03") == "BZH27" and ST.raw_symbols("CORN", "2027-03") == ["ZCH7", "ZCH27"]
    assert ST.notice_date("BRENT", 2027, 3) == date(2027, 1, 31)
    assert ST.notice_date("GOLD", 2026, 12) == date(2026, 11, 30)
    assert ST.front_month("GOLD", date(2026, 11, 6)) == "2027-02"          # Dec notice 30 Nov is within 35 days
    assert ST.front_month("CORN", date(2026, 11, 6)) == "2027-03"
    assert ST.front_month("WTI", date(2026, 11, 6)) == "2027-01"


# ----------------------------------------------------------------------------- Janus sessions: read-only clone
import subprocess
from pathlib import Path


def _bare_data_repo(tmp_path):
    src = tmp_path / "src"
    (src / "ledger").mkdir(parents=True)
    (src / "ledger/futures_settlements.csv").write_text(",".join(ST.SETTLE_COLUMNS) + "\n2026-11-05,BRENT,2027-03,92.5,x,,t,\n")
    (src / "norgate").mkdir()
    (src / "norgate/big.csv").write_text("not needed by Janus\n")
    g = lambda *a, cwd=src: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)
    g("init", "-q", "-b", "main")
    g("-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x")
    bare = tmp_path / "data.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(src), str(bare)], check=True)
    subprocess.run(["git", "config", "uploadpack.allowFilter", "true"], cwd=bare, check=True)
    return bare


def test_read_only_clone_never_exposes_the_token_and_refuses_writes(tmp_path, monkeypatch):
    bare = _bare_data_repo(tmp_path)
    root = tmp_path / "work/em-macro"
    root.mkdir(parents=True)
    secret = "github_pat_SECRET_0123456789"
    monkeypatch.delenv("EM_MACRO_DATA", raising=False)
    monkeypatch.setenv("DATA_REPO_URL", f"file://{bare}")
    monkeypatch.setenv(ST.TOKEN_ENV, secret)
    seen = []

    def run(cmd, **kw):
        seen.append((cmd, kw["env"]))
        return subprocess.run(cmd, **kw)
    store, status = ST.ensure_read_only_store(root, run=run)
    assert store == tmp_path / "work/em-macro-data" and "read-only clone" in status and secret not in status
    assert status.endswith("(environment credentials)")          # route 1: no header sent at all
    assert all("extraheader" not in " ".join(v for k, v in env.items() if k.startswith("GIT_CONFIG_KEY")) for _cmd, env in seen)
    assert ST.read(store)[0]["settle"] == "92.5" and not (store / "norgate").exists()        # sparse: ledger/ only
    for cmd, env in seen:
        assert not any(secret in c for c in cmd) and ST.TOKEN_ENV not in env                  # never on a command line
    assert secret not in (store / ".git/config").read_text()
    push = subprocess.run(["git", "remote", "get-url", "--push", "origin"], cwd=store, capture_output=True, text=True).stdout
    assert "DISABLED" in push
    with pytest.raises(ST.ReadOnlyStore):
        ST.write(store, [{"date": "2026-11-06", "product": "BRENT", "contract_month": "2027-03", "settle": "1"}])
    res = ST.fetch({("BRENT", "2027-03"): date(2026, 11, 6)}, date(2026, 11, 10), store, c=FakeClient(ROWS))
    assert res["stored"] == 0 and "read-only" in res["log"][0] and not (store / ST.SPEND_FILE).exists()
    # a second call refreshes the clone; a failure message is redacted
    store2, status2 = ST.ensure_read_only_store(root, run=run)
    assert store2 == store and status2 == "read-only clone refreshed (environment credentials)"


def test_clone_failure_is_redacted(tmp_path, monkeypatch):
    secret = "github_pat_SECRET_9"
    monkeypatch.delenv("EM_MACRO_DATA", raising=False)
    monkeypatch.setenv(ST.TOKEN_ENV, secret)

    class R:
        returncode, stdout = 128, ""
        stderr = f"fatal: Authentication failed for https://x-access-token:{secret}@github.com/"
    store, status = ST.ensure_read_only_store(tmp_path / "em-macro", run=lambda cmd, **kw: R())
    assert store is None and "could not clone" in status and secret not in status and "***" in status


def test_existing_writable_store_is_used_as_is(tmp_path, monkeypatch):
    (tmp_path / "em-macro-data").mkdir()
    monkeypatch.delenv("EM_MACRO_DATA", raising=False)
    monkeypatch.setenv(ST.TOKEN_ENV, "x")
    store, status = ST.ensure_read_only_store(tmp_path / "em-macro", run=lambda *a, **k: pytest.fail("no git call"))
    assert store == tmp_path / "em-macro-data" and status == "private store present"


def test_token_route_is_the_fallback_when_environment_credentials_fail(tmp_path, monkeypatch):
    bare = _bare_data_repo(tmp_path)
    root = tmp_path / "work/em-macro"
    root.mkdir(parents=True)
    monkeypatch.delenv("EM_MACRO_DATA", raising=False)
    monkeypatch.setenv("DATA_REPO_URL", f"file://{bare}")
    monkeypatch.setenv(ST.TOKEN_ENV, "github_pat_SECRET_X")
    calls = []

    def header(env):
        return next((env[k.replace("KEY", "VALUE")] for k, v in env.items()
                     if k.startswith("GIT_CONFIG_KEY") and v.endswith(".extraheader")), "")

    def run(cmd, **kw):
        calls.append(header(kw["env"]))
        if cmd[1] == "clone" and not header(kw["env"]):
            class R:
                returncode, stdout, stderr = 128, "", "remote: Repository not found. fatal: 403"
            return R()
        return subprocess.run(cmd, **kw)
    store, status = ST.ensure_read_only_store(root, run=run)
    assert store is not None and status.endswith(f"({ST.TOKEN_ENV})")
    assert calls[0] == "" and calls[1].startswith("AUTHORIZATION: basic ")
    assert "github_pat_SECRET_X" not in status


def test_failure_names_the_github_app_fix(tmp_path, monkeypatch):
    monkeypatch.delenv("EM_MACRO_DATA", raising=False)
    monkeypatch.delenv(ST.TOKEN_ENV, raising=False)

    class R:
        returncode, stdout, stderr = 128, "", "fatal: unable to access: The requested URL returned error: 403"
    store, status = ST.ensure_read_only_store(tmp_path / "em-macro", run=lambda cmd, **kw: R())
    assert store is None and "github.com/settings/installations" in status and "environment credentials" in status


def test_process_read_only_refuses_writes_to_any_store(tmp_path, monkeypatch):
    monkeypatch.setattr(ST, "_PROCESS_READ_ONLY", False)
    ST.write(tmp_path, [{"date": "2026-11-06", "product": "BRENT", "contract_month": "2027-03", "settle": "1"}])
    ST.set_read_only()
    with pytest.raises(ST.ReadOnlyStore):
        ST.write(tmp_path, [{"date": "2026-11-09", "product": "BRENT", "contract_month": "2027-03", "settle": "1"}])
    res = ST.fetch({("BRENT", "2027-03"): date(2026, 11, 6)}, date(2026, 11, 10), tmp_path, c=FakeClient(ROWS))
    assert res["stored"] == 0 and "read-only" in res["log"][0]


def test_token_route_keeps_the_environments_git_config(tmp_path, monkeypatch):
    monkeypatch.delenv("EM_MACRO_DATA", raising=False)
    monkeypatch.setenv(ST.TOKEN_ENV, "t")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "credential.interactive")
    monkeypatch.setenv("GIT_CONFIG_KEY_1", "url.https://github.com/.insteadOf")
    envs = []

    class R:
        returncode, stdout, stderr = 128, "", "fatal: 403"

    def run(cmd, **kw):
        envs.append(kw["env"])
        return R()
    ST.ensure_read_only_store(tmp_path / "em-macro", run=run)
    tok = envs[-1]
    assert tok["GIT_CONFIG_COUNT"] == "3" and tok["GIT_CONFIG_KEY_0"] == "credential.interactive"
    assert tok["GIT_CONFIG_KEY_1"] == "url.https://github.com/.insteadOf"
    assert tok["GIT_CONFIG_KEY_2"] == "http.https://github.com/.extraheader"

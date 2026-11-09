"""CME-group futures settlements by contract month, from Databento, stored only in the private data repository.

    python -m ledger.settlements fetch            # every contract month the books need: final settlements since
                                                  # each one's start, quoted first, within the US$1 daily cap
    python -m ledger.settlements fetch --dry-run  # quote only
    python -m ledger.settlements spend            # today's Databento spend against the cap

**Source.** Databento GLBX.MDP3 (CME Globex MDP 3.0), schema ``statistics``: the **final** settlement price of each
contract and trading date (stat_type 3 with the final bit of stat_flags set; the preliminary one CME sends first
is ignored). It reuses em_macro/commod_databento.py (client, dataset, schema, ``final_settlements``). The CME
website fetch was dropped on 2026-11-06: cmegroup.com refused or held every scripted request, and from GitHub
Actions each of the five daily requests ran into the 60-second timeout.

**Licence.** Databento passes on CME's licence terms. Settlements are therefore stored only in the private
repository em-macro-data (``ledger/futures_settlements.csv``, located by ``EM_MACRO_DATA`` or
``../em-macro-data``). This repository publishes only P&L in % of account: data/ledger/derivative_pnl.csv for my
decisions and data/janus/futures_pnl.csv for Janus.

**Cost guard.** Every request is quoted with ``metadata.get_cost`` before it is sent. A request is refused when
today's (UTC) spend plus its quote would exceed US$1.00. The cap is shared by every caller: my futures and options
marks and Janus's. Each quote, request and refusal is logged in ``ledger/databento_spend.jsonl`` in the private
store. Without a private store nothing is fetched, because the spend could not be tracked.

**Janus sessions** read the store through a read-only clone (``ensure_read_only_store``: the environment's own
GitHub credentials first, which is the only route behind the Claude Code git proxy, then ``DATA_REPO_READ_TOKEN``
where no such proxy exists), and never write to it: the Janus CLI marks its process read-only. Only ledger-daily
fetches.

**Availability.** Databento's historical GLBX data runs a few hours behind real time. A day's final settlement
(sent by CME after about 00:30 UTC the next day) is usually available by about 09:00 UTC, so the 09:22 UTC backup
run of ledger-daily picks it up when the 05:52 run is too early. Requests end at the dataset's available end.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAILY_CAP_USD = 1.00
REFETCH_DAYS = 7          # days before the last stored settlement that every fetch requests again (late finals)
SETTLE_FILE = "ledger/futures_settlements.csv"
SPEND_FILE = "ledger/databento_spend.jsonl"
SETTLE_COLUMNS = ["date", "product", "contract_month", "settle", "source", "source_url", "fetched_at", "note"]
MONTH_CODES = "FGHJKMNQUVXZ"
ALL = MONTH_CODES
SOURCE = "Databento GLBX.MDP3 statistics, final settlement"

# product -> Globex contract. Prices in Databento's units (as quoted on Globex): USD per unit for energy and metals,
# US cents per bushel for grains. ``multiplier`` = US$ per 1.0 of that price per contract (grains: 5,000 bu x
# US$0.01 = 50). ``tick``/``tick_value`` as on CME. ``months`` = listed months used by the roll rule.
CONTRACTS = {
    "WTI": dict(root="CL", name="NYMEX WTI crude oil (CL)", exchange="NYMEX", sector="energy", unit="USD per bbl",
                multiplier=1000, tick=0.01, tick_value=10.0, months=ALL, notice="cl"),
    "BRENT": dict(root="BZ", name="NYMEX Brent Last Day Financial (BZ), proxy for ICE Brent crude", exchange="NYMEX",
                  sector="energy", unit="USD per bbl", multiplier=1000, tick=0.01, tick_value=10.0, months=ALL,
                  notice="brent", proxy=True, proxy_for="ICE Brent crude"),
    "NATGAS": dict(root="NG", name="NYMEX Henry Hub natural gas (NG)", exchange="NYMEX", sector="energy",
                   unit="USD per MMBtu", multiplier=10000, tick=0.001, tick_value=10.0, months=ALL, notice="ng"),
    "HEATOIL": dict(root="HO", name="NYMEX NY Harbor ULSD (HO)", exchange="NYMEX", sector="energy", unit="USD per gal",
                    multiplier=42000, tick=0.0001, tick_value=4.2, months=ALL, notice="eom_prev"),
    "RBOB": dict(root="RB", name="NYMEX RBOB gasoline (RB)", exchange="NYMEX", sector="energy", unit="USD per gal",
                 multiplier=42000, tick=0.0001, tick_value=4.2, months=ALL, notice="eom_prev"),
    "GOLD": dict(root="GC", name="COMEX gold (GC)", exchange="COMEX", sector="metals", unit="USD per oz",
                 multiplier=100, tick=0.10, tick_value=10.0, months="GJMQVZ", notice="lbd_prev"),
    "SILVER": dict(root="SI", name="COMEX silver (SI)", exchange="COMEX", sector="metals", unit="USD per oz",
                   multiplier=5000, tick=0.005, tick_value=25.0, months="HKNUZ", notice="lbd_prev"),
    "COPPER": dict(root="HG", name="COMEX copper (HG)", exchange="COMEX", sector="metals", unit="USD per lb",
                   multiplier=25000, tick=0.0005, tick_value=12.5, months="HKNUZ", notice="lbd_prev"),
    "CORN": dict(root="ZC", name="CBOT corn (ZC)", exchange="CBOT", sector="grains", unit="US cents per bu",
                 multiplier=50, tick=0.25, tick_value=12.5, months="HKNUZ", notice="lbd_prev"),
    "SOYBEANS": dict(root="ZS", name="CBOT soybeans (ZS)", exchange="CBOT", sector="grains", unit="US cents per bu",
                     multiplier=50, tick=0.25, tick_value=12.5, months="FHKNQUX", notice="lbd_prev"),
    "WHEAT": dict(root="ZW", name="CBOT Chicago SRW wheat (ZW)", exchange="CBOT", sector="grains", unit="US cents per bu",
                  multiplier=50, tick=0.25, tick_value=12.5, months="HKNUZ", notice="lbd_prev"),
}
NOTICE_TEXT = {
    "cl": "the 20th of the month before delivery (CL last trade: 3 business days before the 25th)",
    "brent": "the last day of the second month before delivery (ICE Brent last trade; BZ settles to it)",
    "ng": "the 26th of the month before delivery (NG last trade: 3 business days before the 1st)",
    "eom_prev": "the last day of the month before delivery (last trade)",
    "lbd_prev": "the last business day of the month before delivery (first notice day)",
}


# ----------------------------------------------------------------------------- contract calendar
def _add_months(y: int, m: int, k: int) -> tuple[int, int]:
    n = y * 12 + (m - 1) + k
    return n // 12, n % 12 + 1


def notice_date(product: str, y: int, m: int) -> date:
    """Approximate notice (or last trade) date of the (y, m) contract: NOTICE_TEXT."""
    rule = CONTRACTS[product]["notice"]
    if rule == "cl":
        py, pm = _add_months(y, m, -1)
        return date(py, pm, 20)
    if rule == "ng":
        py, pm = _add_months(y, m, -1)
        return date(py, pm, 26)
    if rule == "brent":
        py, pm = _add_months(y, m, -2)
        return date(py, pm, calendar.monthrange(py, pm)[1])
    py, pm = _add_months(y, m, -1)
    d = date(py, pm, calendar.monthrange(py, pm)[1])
    if rule == "lbd_prev":
        while d.weekday() >= 5:
            d -= timedelta(days=1)
    return d


def listed(product: str, y: int, m: int) -> bool:
    return MONTH_CODES[m - 1] in CONTRACTS[product]["months"]


def front_month(product: str, d: date, buffer_days: int = 35, skip: int = 0) -> str:
    """The earliest listed contract month whose notice date is more than ``buffer_days`` after ``d`` ('YYYY-MM');
    ``skip`` = 1 gives the next one."""
    found = 0
    for k in range(0, 30):
        y, m = _add_months(d.year, d.month, k)
        if listed(product, y, m) and notice_date(product, y, m) > d + timedelta(days=buffer_days):
            if found == skip:
                return f"{y}-{m:02d}"
            found += 1
    raise ValueError(f"no {product} contract found after {d}")


def contract_code(product: str, month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{CONTRACTS[product]['root']}{MONTH_CODES[m - 1]}{str(y)[-2:]}"


def raw_symbols(product: str, month: str) -> list[str]:
    """Globex raw symbols to try: one-digit year first, then two (NG and far months use two)."""
    y, m = int(month[:4]), int(month[5:7])
    base = f"{CONTRACTS[product]['root']}{MONTH_CODES[m - 1]}"
    return [f"{base}{y % 10}", f"{base}{y % 100:02d}"]


# ----------------------------------------------------------------------------- private store
DATA_REPO = "EthanC100/em-macro-data"
TOKEN_ENV = "DATA_REPO_READ_TOKEN"          # fine-grained, read-only token of the Janus cloud environment
READ_ONLY_MARK = ".ledger-read-only-clone"  # in a clone made by ensure_read_only_store: every write is refused


class ReadOnlyStore(RuntimeError):
    pass


def store_dir(root: Path = ROOT) -> Path | None:
    p = Path(os.environ.get("EM_MACRO_DATA") or (root.parent / "em-macro-data"))
    return p if p.is_dir() else None


_PROCESS_READ_ONLY = False   # set by set_read_only(): every write from this process is refused (Janus CLI)


def set_read_only() -> None:
    """Refuse every write to the private store from this process, however the store got here (the Janus CLI
    calls it: Janus only reads settlements)."""
    global _PROCESS_READ_ONLY
    _PROCESS_READ_ONLY = True


def is_read_only(store: Path | None) -> bool:
    return _PROCESS_READ_ONLY or (bool(store) and (store / READ_ONLY_MARK).exists())


def _guard_write(store: Path) -> None:
    if is_read_only(store):
        raise ReadOnlyStore(f"{store}: the private store is read-only here (a Janus session): nothing is written to it")


def _redact(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "***")
    return text


def ensure_read_only_store(root: Path = ROOT, run=None) -> tuple[Path | None, str]:
    """For Janus sessions: make sure the private settlements are readable. An existing store is used as it is.
    Otherwise em-macro-data is cloned read-only (sparse: ``ledger/`` only, depth 1) next to this repository, or at
    ``EM_MACRO_DATA``, or an earlier read-only clone is refreshed. Routes, in order:

    1. **The environment's own GitHub credentials.** In Claude Code cloud sessions, the egress proxy supplies them
       for the repositories the Claude GitHub App may access. It **replaces** any Authorization header a client
       sends, so a token cannot help there. This is the route that works once em-macro-data is included in the
       app's repository access.
    2. **DATA_REPO_READ_TOKEN** (a fine-grained read-only token), sent as an HTTP header through GIT_CONFIG_*
       environment variables, for environments without such a proxy. It never appears in a URL, .git/config, a
       command line or any output, and git output is redacted.

    The clone's push URL is disabled and a marker file makes every write refuse. Returns (store or None, a one-line
    status without the token)."""
    import base64
    import subprocess
    existing = store_dir(root)
    if existing and not (existing / READ_ONLY_MARK).exists():
        return existing, "private store present"
    run = run or subprocess.run
    target = Path(os.environ.get("EM_MACRO_DATA") or (root.parent / "em-macro-data"))
    url = os.environ.get("DATA_REPO_URL") or f"https://github.com/{DATA_REPO}.git"
    token = os.environ.get(TOKEN_ENV, "").strip()
    base_env = {k: v for k, v in os.environ.items() if k != TOKEN_ENV}
    base_env["GIT_TERMINAL_PROMPT"] = "0"
    routes = [("environment credentials", dict(base_env))]
    secrets = []
    if token:
        b64 = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        secrets = [token, b64]
        n = int(base_env.get("GIT_CONFIG_COUNT") or 0)       # append to the environment's own GIT_CONFIG_* entries
        routes.append((TOKEN_ENV, {**base_env, "GIT_CONFIG_COUNT": str(n + 1),
                                   f"GIT_CONFIG_KEY_{n}": "http.https://github.com/.extraheader",
                                   f"GIT_CONFIG_VALUE_{n}": f"AUTHORIZATION: basic {b64}"}))

    def git(env, *args, cwd=None):
        r = run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True)
        return r.returncode, _redact((r.stdout or "") + (r.stderr or ""), secrets).strip()

    errors = []
    if existing:                                        # an earlier read-only clone: refresh it
        for name, env in routes:
            code, out = git(env, "fetch", "-q", "--depth", "1", "origin", "main", cwd=existing)
            if code == 0:
                code, out = git(env, "reset", "-q", "--hard", "FETCH_HEAD", cwd=existing)
            if code == 0:
                return existing, f"read-only clone refreshed ({name})"
            errors.append(f"{name}: {out[:160]}")
        return existing, "read-only clone not refreshed: " + "; ".join(errors)
    for name, env in routes:
        code, out = git(env, "clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse", "--branch", "main", url,
                        str(target))
        if code == 0:
            git(env, "sparse-checkout", "set", "ledger", cwd=target)
            git(env, "remote", "set-url", "--push", "origin", "DISABLED-read-only-clone", cwd=target)
            (target / READ_ONLY_MARK).write_text("Read-only clone for a Janus session. Never commit or push from here.\n")
            excl = target / ".git/info/exclude"
            excl.parent.mkdir(parents=True, exist_ok=True)
            with excl.open("a") as f:
                f.write(f"\n{READ_ONLY_MARK}\n")
            return target, f"read-only clone of {DATA_REPO} made at {target} ({name})"
        errors.append(f"{name}: {out[:160]}")
        if target.exists() and not any(target.iterdir()):
            target.rmdir()
    hint = ("; behind the Claude Code git proxy this means em-macro-data is not in the session's repositories: the "
            "Claude GitHub App needs access to it (github.com/settings/installations, Claude, Repository access), then "
            "add it to the Janus environment's repositories, or attach it in the session (add_repo, read access)")
    return None, f"could not clone {DATA_REPO} read-only: " + "; ".join(errors) + hint


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def read(store: Path | None) -> list[dict]:
    return _rows(store / SETTLE_FILE) if store else []


def write(store: Path, new: list[dict]) -> int:
    _guard_write(store)
    path = store / SETTLE_FILE
    keyed = {(r["product"], r["contract_month"], r["date"]): r for r in _rows(path)}
    n = 0
    for r in new:
        k = (r["product"], r["contract_month"], r["date"])
        if keyed.get(k, {}).get("settle") != r["settle"]:
            n += 1
        keyed[k] = {c: r.get(c, "") for c in SETTLE_COLUMNS}
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SETTLE_COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in sorted(keyed.values(), key=lambda r: (r["date"], r["product"], r["contract_month"])):
            w.writerow(r)
    return n


def series(rows: list[dict], product: str, month: str) -> list[tuple[date, float, dict]]:
    out = {}
    for r in rows:
        if r.get("product") == product and r.get("contract_month") == month and r.get("settle"):
            d = date.fromisoformat(r["date"])
            out[d] = (d, float(r["settle"]), r)
    return [out[k] for k in sorted(out)]


def on_or_before(rows: list[dict], product: str, month: str, d: date):
    best = None
    for x in series(rows, product, month):
        if x[0] <= d:
            best = x
    return best


# ----------------------------------------------------------------------------- spend guard
def spent_today(store: Path, today: date) -> float:
    p = store / SPEND_FILE
    if not p.exists():
        return 0.0
    tot = 0.0
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r.get("downloaded") and r.get("utc_date") == today.isoformat():
                tot += float(r.get("quote_usd") or 0)
    return tot


def _log_spend(store: Path, rec: dict) -> None:
    _guard_write(store)
    p = store / SPEND_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


# ----------------------------------------------------------------------------- fetch
def client():
    from em_macro.commod_databento import client as _client
    return _client()


def _parse_end(end) -> datetime:
    s = str(end).replace("Z", "")
    if "+" in s[19:]:
        s = s[:s.index("+", 19)]
    s = s[:26]
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def fetch(needs: dict[tuple[str, str], date], today: date | None = None, store: Path | None = None,
          cap: float = DAILY_CAP_USD, c=None, dry_run: bool = False, purpose: str = "ledger") -> dict:
    """Final settlements for ``needs`` {(product, 'YYYY-MM'): first date wanted} into the private store, in one
    request quoted first. Returns {"stored": n, "quote_usd": q, "log": [...], "refused": bool}."""
    from em_macro.commod_databento import DATASET, SCHEMA, final_settlements
    today = today or datetime.now(timezone.utc).date()
    store = store if store is not None else store_dir()
    out = {"stored": 0, "quote_usd": 0.0, "log": [], "refused": False}
    if store is None:
        out["log"].append("no private store (EM_MACRO_DATA / ../em-macro-data): nothing fetched")
        return out
    if is_read_only(store):
        out["log"].append("read-only clone (a Janus session): settlements are fetched only by ledger-daily")
        return out
    if not needs:
        out["log"].append("no contract months needed")
        return out
    try:
        c = c or client()
        end = _parse_end((c.metadata.get_dataset_range(dataset=DATASET).get("schema", {}).get(SCHEMA) or {}).get("end"))
    except Exception as e:  # noqa: BLE001
        out["log"].append(f"Databento unavailable: {str(e)[:200]}")
        return out
    have = read(store)
    starts = {}
    for (prod, month), first in needs.items():
        last = max((x[0] for x in series(have, prod, month)), default=None)
        # the last REFETCH_DAYS days are always requested again: a final settlement can arrive days late (a Friday's
        # on the Sunday) or be republished after Databento withdraws a day, after a later day is already stored
        st = max(first, last + timedelta(days=1) - timedelta(days=REFETCH_DAYS)) if last else first
        if st <= end.date():
            starts[(prod, month)] = st
    if not starts:
        out["log"].append("all needed settlements already stored")
        return out
    start = min(starts.values())
    try:
        cand = {s: k for k in starts for s in raw_symbols(*k)}
        r = c.symbology.resolve(dataset=DATASET, symbols=list(cand), stype_in="raw_symbol", stype_out="instrument_id",
                                start_date=start.isoformat(), end_date=end.date().isoformat())
        found = {k for k, v in (r.get("result") or {}).items() if v} - set(r.get("not_found") or [])
        chosen = {}
        for s, k in cand.items():
            if s in found and k not in chosen.values():
                chosen[s] = k
        missing = sorted(f"{p} {m}" for (p, m) in starts if (p, m) not in chosen.values())
        if missing:
            out["log"].append("not on Globex for these dates: " + ", ".join(missing))
        if not chosen:
            return out
        kw = dict(dataset=DATASET, symbols=sorted(chosen), stype_in="raw_symbol", schema=SCHEMA,
                  start=f"{start.isoformat()}T00:00:00Z", end=end.strftime("%Y-%m-%dT%H:%M:%SZ"))
        quote = float(c.metadata.get_cost(**kw))
    except Exception as e:  # noqa: BLE001
        out["log"].append(f"Databento request could not be prepared: {str(e)[:200]}")
        return out
    out["quote_usd"] = quote
    spent = spent_today(store, today)
    rec = {"utc_date": today.isoformat(), "time": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
           "purpose": purpose, "symbols": sorted(chosen), "start": kw["start"], "end": kw["end"], "quote_usd": quote}
    if spent + quote > cap + 1e-12:
        out["refused"] = True
        _log_spend(store, {**rec, "downloaded": False, "reason": f"daily cap US${cap:.2f} (spent US${spent:.4f})"})
        out["log"].append(f"refused: quote US${quote:.4f} would take today's spend above US${cap:.2f} (spent US${spent:.4f})")
        return out
    if dry_run:
        out["log"].append(f"dry run: {len(chosen)} symbol(s) from {start}, quote US${quote:.6f}")
        return out
    try:
        df = c.timeseries.get_range(**kw).to_df(map_symbols=True)
    except Exception as e:  # noqa: BLE001
        _log_spend(store, {**rec, "downloaded": False, "reason": str(e)[:200]})
        out["log"].append(f"Databento request failed: {str(e)[:200]}")
        return out
    _log_spend(store, {**rec, "downloaded": True})
    fs = final_settlements(df)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    new = []
    for sym, d, px in zip(fs["symbol"], fs["date"], fs["settle"]):
        k = chosen.get(sym)
        if not k or d < starts[k]:
            continue
        prod, month = k
        new.append({"date": d.isoformat(), "product": prod, "contract_month": month, "settle": f"{px:.10g}",
                    "source": f"{SOURCE} ({CONTRACTS[prod]['exchange']} {sym})", "source_url": "https://databento.com",
                    "fetched_at": now, "note": ""})
    out["stored"] = write(store, new) if new else 0
    out["log"].append(f"{len(chosen)} symbol(s) from {start}: {len(new)} final settlement(s), {out['stored']} new; "
                      f"quote US${quote:.6f}, spent today US${spent + quote:.4f} of US${cap:.2f}")
    return out


def needs_all(root: Path = ROOT, today: date | None = None) -> dict[tuple[str, str], date]:
    """Every contract month the books need: my open futures/options decisions (from their entry date) and Janus's
    pending or open futures/options positions (from the decision date: the held contract and the next one), plus
    the front and next contract of each Janus futures market over the last 10 days, for the daily review."""
    from . import derivs as DV
    today = today or date.today()
    needs: dict[tuple[str, str], date] = {}

    def add(k, d):
        if k[0] in CONTRACTS:
            needs[k] = min(needs.get(k, d), d)
    decisions = {r["id"]: r for r in _rows(root / "data/ledger/decisions.csv")}
    for i, t in DV.load_terms(root).items():
        if (decisions.get(i, {}).get("status") or "open").lower() == "open":
            add((t["product"], t["contract_month"]), date.fromisoformat(t["entry_date"]))
    try:
        from . import janus as JN
        for k, d in JN.futures_needs(JN.load(root / "data/janus/records.jsonl"), today).items():
            add(k, d)
    except (ImportError, AttributeError, FileNotFoundError):
        pass
    for prod in CONTRACTS:
        for skip in (0, 1):
            add((prod, front_month(prod, today, skip=skip)), today - timedelta(days=10))
    return needs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["fetch", "spend"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--today", default=None)
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else datetime.now(timezone.utc).date()
    store = store_dir()
    if a.cmd == "spend":
        print(json.dumps({"store": bool(store), "spent_today_usd": spent_today(store, today) if store else None,
                          "cap_usd": DAILY_CAP_USD}))
        return 0
    res = fetch(needs_all(today=today), today, store, dry_run=a.dry_run)
    print("\n".join(res["log"]))
    print(json.dumps({k: res[k] for k in ("stored", "quote_usd", "refused")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

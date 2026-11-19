"""Synthetic fixtures for the S16 acceptance suite. Hand-made values only: no market data is read or written.

Imported lazily by tests whose capabilities are present (the modules it touches exist only when the PRs merge).
"""
from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone

import numpy as np

H = lambda s: hashlib.sha256(s.encode()).hexdigest()          # noqa: E731

# ------------------------------------------------------------------------------------------- PR #86 (access, attempts)

DOM = "s16_synthetic"
EXPLORE_END = date(2009, 12, 31)
RESERVE = (date(2010, 1, 4), date(2010, 3, 31))
FREEZE = date(2010, 1, 3)
SPECS = {level: {"level": level, "fixture": "S16 acceptance synthetic"}
         for level in ("executable", "variant", "hypothesis", "family")}


def fences():
    from manhattan import roles
    open_ = roles.Fence(exploration_end=EXPLORE_END, reserve={}, enabled=False)
    reserve = roles.Fence(exploration_end=EXPLORE_END, reserve={DOM: RESERVE}, enabled=True)
    return open_, reserve


def pit_store(start=date(2009, 11, 2), n=60, synthetic=False):
    """A fabricated price series (a deterministic ramp) in a PIT store."""
    from manhattan.engine import pit
    s = pit.PitStore(synthetic=synthetic)
    days = np.array([d for d in np.arange(np.datetime64(start), np.datetime64(start) + np.timedelta64(120, "D"))
                     if np.is_busday(d)][:n], dtype="datetime64[D]")
    s.add("A", days, 100.0 + np.arange(days.size), lag_days=0)
    return s


def hold():
    from manhattan.engine.backtest import Instrument, Strategy
    return Strategy((Instrument("A", "A"),), lambda v: {"A": 1.0}, rebalance="D", lag=0)


def ledger(path):
    from manhattan import ledger as L
    return L.Ledger(path, writer="s16-acceptance", protocol="0" * 64)


def anchor(book) -> dict:
    return {"records": len(book), "head": book.head}


def spec_kwargs(specs=SPECS, *, batch="S16-0001", channel="blind", designated=False) -> dict:
    return {**specs, "batch": batch, "channel": channel, "designated": designated}


def identity(store, *, start, end, role, specs=SPECS, batch="S16-0001", designated=False, window_id=None):
    from manhattan import spec
    from manhattan.engine import evaluate
    wid = window_id or f"{DOM}:{start}:{end}"
    return {"executable": spec.spec_id(specs["executable"]), "variant": spec.spec_id(specs["variant"]),
            "hypothesis": spec.spec_id(specs["hypothesis"]), "family": spec.spec_id(specs["family"]),
            "batch": batch, "role": role, "channel": "blind", "designated": designated,
            "spec_hash": spec.spec_hash(specs["executable"]), "data_hash": store.data_hash(),
            "window": {"id": wid, "start": str(start), "end": str(end), "frequency": "daily"},
            "code_version": evaluate.code_version()}


def register(book, store, *, start, end, role, fence, caller="runner", freeze=None, token=None, supersedes=None,
             specs=SPECS, designated=False, window_id=None):
    from manhattan import access
    wid = window_id or f"{DOM}:{start}:{end}"
    return access.register_evaluation(
        book, identity=identity(store, start=start, end=end, role=role, specs=specs, designated=designated,
                                window_id=wid),
        windows=[access.DeclaredWindow(wid, DOM, start, end, role, "evaluation", store.data_hash())],
        caller=caller, fence=fence, freeze=freeze, token=token, supersedes=supersedes)


def reserve_token(window_id, batch="S16-0001"):
    from manhattan import roles, spec
    return roles.RunnerToken(batch, "f" * 64, True, frozenset({(DOM, window_id)}),
                             frozenset({spec.spec_hash(SPECS["executable"])}))


# ---------------------------------------------------------------------------------------------- PR #84 (evidence)

def publication_contract():
    return {"name": "hte-synthetic", "frequency": "daily", "period_label": "observation_date",
            "availability": {"kind": "daily_lag", "reference": "synthetic fixture", "day_mapping": "close"},
            "publication_lag_days": 1}


def hte_evidence_metadata(panel, run_id: str) -> dict:
    """Evidence metadata (manhattan.evidence schema) describing an HTE synthetic run, as an adapter would state it.
    No adapter produces this today (integration gap GAP-03); the acceptance suite builds it by hand to show what the
    classifier does with HTE output."""
    from manhattan import evidence as E
    dates = panel.dates
    start, end = str(dates[0]), str(dates[panel.fence - 1])
    return {"schema": E.SCHEMA,
            "source": {"id": "hte-synthetic", "kind": "synthetic", "publication_contract": publication_contract()},
            "domain": "fx_daily", "span": {"start": start, "end": end},
            "vintage": {"kind": "generated", "id": panel.data_hash, "as_of": end},
            "spec": {"spec_hash": H(run_id), "channel": "blind", "freeze": None, "holding_periods": 0},
            "window": {"id": run_id}, "designated": False}


def stand_in_panel():
    """Hand-made dates and data hash in the shape ``hte_evidence_metadata`` reads (no generator needed)."""
    class _Panel:
        dates = np.array([date(2001, 1, 2) + timedelta(days=i) for i in range(400)])
        fence = 400
        data_hash = H("s16-stand-in-panel")
    return _Panel


def honest_synthetic_results(md, authority: str):
    from manhattan import evidence as E
    subject = E.subject_digest(md)
    sp, span, vin = md["spec"], md["span"], md["vintage"]
    facts = {"spec_registry": {"spec_hash": sp["spec_hash"], "channel": sp["channel"], "domain": md["domain"],
                               "holding_periods": sp["holding_periods"]},
             "synthetic_generator": {"vintage_id": vin["id"], "observed_start": span["start"],
                                     "observed_end": span["end"]}}
    return [E.VerifierResult(n, authority, subject, f) for n, f in facts.items()]


def evidence_fence():
    from manhattan import roles
    return roles.Fence(exploration_end=date(2019, 12, 31), reserve={"fx_daily": (date(2020, 3, 2),
                                                                              date(2024, 12, 31))}, enabled=False)


# --------------------------------------------------------------------------------------------- PR #85 (execution)

UTC = timezone.utc


def execution_world(n_days: int = 10):
    from manhattan import execution as X
    days, d = [], date(2027, 1, 4)
    while len(days) < n_days:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    close = lambda d: datetime(d.year, d.month, d.day, 19, 30, tzinfo=UTC)          # noqa: E731
    published = lambda d: datetime(d.year, d.month, d.day, 21, 0, tzinfo=UTC)       # noqa: E731
    spec = X.ContractSpec(contract_id=X.contract_id("SYNA", "2027-04"), root="SYNA", exchange="SYNX",
                          delivery_month="2027-04", currency="USD", tick_size=0.01, tick_value=10.0,
                          multiplier=1000.0, price_unit_value=1.0, first_trade=date(2026, 1, 2),
                          last_trade=date(2027, 3, 27), settlement_type="physical", first_notice=date(2027, 3, 25),
                          initial_margin=5000.0)
    px = [X.Settlement(spec.contract_id, d, round(50.0 + 0.10 * i, 2), published(d)) for i, d in enumerate(days)]
    liq = X.Liquidity(spec.contract_id, 1000.0, 0.8, datetime(2026, 12, 31, tzinfo=UTC))
    market = X.MarketData(calendar=[X.TradingDay(d, close(d)) for d in days], contracts=[spec], settlements=px,
                          liquidity=[liq])
    terms = X.CostTerms(fee_currency="USD", commission_per_contract=1.0, exchange_fee_per_contract=0.5,
                        half_spread_ticks=0.5, slippage_ticks=0.5, impact_coefficient=0.0, max_participation=0.1,
                        margin_funding_bps_per_year=0.0)
    scenario = X.CostScenario("synthetic base", "synthetic", (("SYNA", terms),))
    policy = X.ExecutionPolicy(base_currency="USD", roll=X.RollPolicy(buffer_days=35, roll_before_notice_days=10))
    return {"days": days, "spec": spec, "market": market, "terms": terms, "scenario": scenario, "policy": policy,
            "liq": liq, "px": px, "close": close, "published": published}

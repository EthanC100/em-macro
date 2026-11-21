"""Manhattan's four research tracks: separately identifiable, separately counted (issue #102). **Dormant.**

    tracks.TRACKS["non_technology_equities"].instruments      # ("equity_common", "equity_adr", "equity_reit")
    tracks.rates_instrument_kind(instrument, roots={"SYNT": "treasury_future"})
    tracks.tally(items)                                       # per-track counts; every track present, none merged

The four tracks:

| track | what it trades | shared pipeline |
|---|---|---|
| ``commodities`` | commodity futures | market data (#92), execution (#85, #93), HTE domain ``commodity`` |
| ``technology_equities`` | US-listed technology common stocks and ADRs | ``manhattan.equities`` |
| ``non_technology_equities`` | US-listed non-technology common stocks, ADRs and REITs | ``manhattan.equities`` (the same code) |
| ``rates`` | **Treasury futures only** | market data (#92), execution (#85, #93), HTE domain ``rates`` |

**Treasury futures are not bonds, and bond ETFs are neither.** The rates track's instrument is the exchange-traded
Treasury future: a deliverable basket, a cheapest-to-deliver bond, conversion factors, roll dates and an exchange
settlement price. A cash Treasury (``marketdata`` ``bond_cash``) is an over-the-counter instrument with clean and
dirty prices, accrued interest and repo financing. A bond ETF is an exchange-listed fund: it has a NAV premium or
discount, an expense ratio and tracking error, and its daily close is not a futures settlement. No result on one of
these three instruments stands for another. Cash bonds and bond ETFs are listed below as instrument kinds of **no
track** until the owner decides otherwise (decisions NT-4 and NT-5).

**Measurable.** Each research item names exactly one track. ``tally`` refuses an item with no track, an unknown
track or several tracks, and always reports all four tracks. A combined portfolio (technology plus
non-technology equities) is a *combination* reported next to its parts, never a fifth track. Its components stay
counted in their own tracks, and nothing is counted twice.

Nothing here reads data, registers or runs anything, or changes a switch. ``ENABLED`` is a constant ``False``: the
registry describes tracks, and it activates none.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

ENABLED = False                 # a constant: describing a track activates nothing
REAL_DATA = False               # no track reads real, licensed, reserve or forward data from this module

COMMODITIES, TECHNOLOGY_EQUITIES, NON_TECHNOLOGY_EQUITIES, RATES = (
    "commodities", "technology_equities", "non_technology_equities", "rates")
TRACK_IDS = (COMMODITIES, TECHNOLOGY_EQUITIES, NON_TECHNOLOGY_EQUITIES, RATES)
COMBINATIONS = MappingProxyType({"combined_equities": (TECHNOLOGY_EQUITIES, NON_TECHNOLOGY_EQUITIES)})


@dataclass(frozen=True)
class InstrumentKind:
    kind: str
    track: str | None               # None: an instrument of no research track (owner decision before any use)
    marketdata_asset_class: str | None
    equity_security_types: tuple
    note: str


INSTRUMENT_KINDS = MappingProxyType({k.kind: k for k in (
    InstrumentKind("commodity_future", COMMODITIES, "future", (),
                   "exchange-traded commodity futures; settlement prices, rolls, contract specifications"),
    InstrumentKind("treasury_future", RATES, "future", (),
                   "exchange-traded Treasury futures: deliverable basket, cheapest-to-deliver, conversion factors, "
                   "roll; priced by exchange settlement"),
    InstrumentKind("cash_bond", None, "bond_cash", (),
                   "cash government bond: OTC, clean/dirty price, accrued interest, repo financing; not a futures "
                   "position and not in the rates track until decided (NT-4)"),
    InstrumentKind("bond_etf", None, None, ("etf",),
                   "exchange-listed bond fund: NAV premium/discount, expense ratio, tracking error; equity-like "
                   "trading; not a Treasury future, not a bond, not an operating company (NT-5)"),
    InstrumentKind("equity_common", None, None, ("common",),
                   "common stock; its equity track is decided by its point-in-time category"),
    InstrumentKind("equity_adr", None, None, ("adr",), "ADR; its equity track is decided by its point-in-time category"),
    InstrumentKind("equity_reit", NON_TECHNOLOGY_EQUITIES, None, ("reit",),
                   "REIT: real-estate sector of the non-technology track (NT-2)"),
)})


@dataclass(frozen=True)
class Track:
    id: str
    title: str
    instruments: tuple
    pipeline: tuple                 # the shared modules the track runs on (descriptive)
    hte_domain: str | None          # the synthetic HTE domain that exercises it, if any
    catalogue: str | None           # hypothesis-family catalogue, if one exists
    status: str = "dormant_synthetic_only"


TRACKS = MappingProxyType({t.id: t for t in (
    Track(COMMODITIES, "Commodity futures", ("commodity_future",),
          ("market data (#92)", "futures execution model (#85)", "execution realism (#93)"),"commodity", None),
    Track(TECHNOLOGY_EQUITIES, "Technology equities", ("equity_common", "equity_adr"),
          ("manhattan.equities",), None, "manhattan/equities/catalogue.yaml"),
    Track(NON_TECHNOLOGY_EQUITIES, "Non-technology equities", ("equity_common", "equity_adr", "equity_reit"),
          ("manhattan.equities",), None, "manhattan/equities/catalogue_nontech.yaml"),
    Track(RATES, "Rates (Treasury futures)", ("treasury_future",),
          ("market data (#92)", "futures execution model (#85)", "execution realism (#93)"),"rates", None),
)})
assert tuple(TRACKS) == TRACK_IDS


class TrackError(ValueError):
    pass


def rates_instrument_kind(instrument, *, roots: dict) -> str:
    """The instrument kind of a ``manhattan.marketdata.schema.Instrument`` for the futures tracks.

    A Treasury future and a commodity future are both ``asset_class="future"``. Which one a root is comes from
    ``roots`` (root -> ``treasury_future`` | ``commodity_future``), a declaration the caller owns. An undeclared root
    is refused, never guessed. A ``bond_cash`` instrument is a ``cash_bond``, which is in no track. Any other asset
    class is refused. A bond ETF cannot arrive here at all: the market-data schema has no fund class."""
    ac = getattr(instrument, "asset_class", None)
    if ac == "bond_cash":
        return "cash_bond"
    if ac != "future":
        raise TrackError(f"asset class {ac!r} is not an instrument of the commodities or rates track")
    kind = roots.get(getattr(instrument, "root", None))
    if kind not in ("treasury_future", "commodity_future"):
        raise TrackError(f"futures root {getattr(instrument, 'root', None)!r} is not declared as a Treasury or "
                         "commodity future")
    return kind


def track_of_instrument_kind(kind: str) -> str | None:
    if kind not in INSTRUMENT_KINDS:
        raise TrackError(f"unknown instrument kind {kind!r}")
    return INSTRUMENT_KINDS[kind].track


def require_track(track) -> str:
    if isinstance(track, (list, tuple, set, frozenset)):
        raise TrackError("an item belongs to exactly one track; a combination is reported separately")
    if track not in TRACK_IDS:
        raise TrackError(f"{track!r} is not a research track ({TRACK_IDS})")
    return track


def tally(items, *, key: str = "track") -> dict:
    """Per-track counts of research items (families, specifications, attempts, results), each naming one track in
    ``key``. All four tracks are always reported, zero included, and the total is their sum. Refuses an item with no
    track, an unknown track or several tracks."""
    counts = {t: 0 for t in TRACK_IDS}
    for it in items:
        counts[require_track(it.get(key) if isinstance(it, dict) else getattr(it, key, None))] += 1
    return {"by_track": counts, "total": sum(counts.values()), "combinations_are_not_tracks": dict(COMBINATIONS)}


def describe() -> dict:
    """The registry as plain data, for reports."""
    return {"enabled": ENABLED, "real_data": REAL_DATA,
            "tracks": {t.id: {"title": t.title, "instruments": list(t.instruments), "pipeline": list(t.pipeline),
                              "hte_domain": t.hte_domain, "catalogue": t.catalogue, "status": t.status}
                       for t in TRACKS.values()},
            "instrument_kinds": {k.kind: {"track": k.track, "marketdata_asset_class": k.marketdata_asset_class,
                                          "equity_security_types": list(k.equity_security_types), "note": k.note}
                                 for k in INSTRUMENT_KINDS.values()},
            "combinations": {k: list(v) for k, v in COMBINATIONS.items()}}

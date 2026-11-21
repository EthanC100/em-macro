"""Sector taxonomy for the shared equity pipeline: the technology and non-technology research universes.

    sectors.sector_of("banks")              # "financials"
    sectors.track_of("banks")               # "non_technology_equities"
    sectors.track_of("semiconductors")      # "technology_equities"

Issue #102 adds **non-technology equities** as its own research track on the *same* equity pipeline (identity,
prices, corporate actions, fundamentals, universe, costs, risk). The two equity tracks differ only in which
point-in-time categories their universes admit. This module is that taxonomy and nothing else: it reads no data and
decides no eligibility.

**Own taxonomy, not a vendor's.** Categories are this package's own sub-industries, as for technology
(``universe.TECH_CATEGORIES``). Vendor industry codes (GICS, ICB, SIC from EDGAR headers) are licensed or coarse; a
source contract maps them onto these categories, and the mapping is a dated record in ``ClassificationHistory``
(``known_from``), never a lookup done today.

**Classification policy (docs/manhattan/equities/NON_TECH_TRACK.md section 3; owner decision NT-1):**

* A company is in exactly one category on any day, so it is in at most one equity track on any day.
* The track follows the category **as known at the formation date**. A company that a vendor later moves from a
  technology category to a non-technology one changes track only from the day the move was published. It is never
  re-filed retroactively, because that would leak the future and quietly move winners or losers between tracks.
* Boundary cases are settled by the package taxonomy, not by vendor sector names. The technology categories
  ``consumer_internet``, ``digital_advertising`` and ``ecommerce`` stay technology even where a vendor files them
  under communication services or consumer discretionary. ``payments`` is financials (non-technology). Telecom
  carriers and traditional media are communication services (non-technology).
* The legacy category ``non_technology`` (one bucket for everything else) stays valid, so old records still load.
  It names **no sector**, so neither equity track admits it: a non-technology company must carry a sector category
  to enter the non-technology universe (fail closed).
* No sector is assumed to be low-volatility. Volatility is measured from the data
  (``track_compare.sector_volatility``).
"""
from __future__ import annotations

from types import MappingProxyType

TECHNOLOGY_TRACK = "technology_equities"
NON_TECHNOLOGY_TRACK = "non_technology_equities"
EQUITY_TRACKS = (TECHNOLOGY_TRACK, NON_TECHNOLOGY_TRACK)
LEGACY_UNASSIGNED = "non_technology"        # the pre-#102 catch-all: valid, but in no sector and no track

# The ten non-technology sectors issue #102 names, each with this package's sub-industry categories.
NON_TECH_SECTORS = MappingProxyType({
    "healthcare": ("pharmaceuticals", "biotechnology", "medical_devices", "healthcare_services", "life_science_tools"),
    "financials": ("banks", "insurance", "capital_markets", "consumer_finance", "payments"),
    "industrials": ("aerospace_defence", "machinery", "transportation", "construction_engineering",
                    "business_services"),
    "utilities": ("electric_utilities", "gas_utilities", "water_utilities", "independent_power"),
    "consumer_staples": ("food_beverage", "household_products", "food_retail", "tobacco"),
    "consumer_discretionary": ("automobiles", "retail_specialty", "apparel", "hotels_leisure", "homebuilders"),
    "materials": ("chemicals", "metals_mining", "construction_materials", "paper_packaging"),
    "energy": ("oil_gas_producers", "oil_gas_services", "refining_marketing", "coal", "midstream"),
    "real_estate": ("equity_reits", "mortgage_reits", "real_estate_operators"),
    "communication_services": ("telecom_carriers", "media_broadcasting", "entertainment_publishing"),
})
NON_TECH_CATEGORIES = tuple(c for cats in NON_TECH_SECTORS.values() for c in cats)
_SECTOR_OF = {c: s for s, cats in NON_TECH_SECTORS.items() for c in cats}
assert len(_SECTOR_OF) == len(NON_TECH_CATEGORIES), "a category belongs to exactly one sector"

# Security types the non-technology universe admits by default. REITs are their own security type in the identity
# layer, and leaving them out would silently empty the real-estate sector (owner decision NT-2).
NON_TECH_SECURITY_TYPES = ("common", "adr", "reit")
# Never an operating company in either equity track: funds, derivatives on shares, and other instruments.
NEVER_IN_EQUITY_TRACKS = ("etf", "unit", "warrant", "right", "preferred", "tracking_stock", "other")


def _tech() -> tuple:
    from .universe import TECH_CATEGORIES          # imported late: universe imports this module
    return TECH_CATEGORIES


def sector_of(category: str | None) -> str | None:
    """The sector of a category. Every technology category is in the sector ``technology``. Returns None for the
    legacy catch-all, for None and for unknown text (the caller treats that as excluded, never as a default)."""
    if category in _tech():
        return "technology"
    return _SECTOR_OF.get(category)


def track_of(category: str | None) -> str | None:
    """The equity research track a category belongs to, or None (legacy catch-all, unknown, no category)."""
    if category in _tech():
        return TECHNOLOGY_TRACK
    if category in _SECTOR_OF:
        return NON_TECHNOLOGY_TRACK
    return None


def categories_of_track(track: str) -> tuple:
    if track == TECHNOLOGY_TRACK:
        return tuple(_tech())
    if track == NON_TECHNOLOGY_TRACK:
        return NON_TECH_CATEGORIES
    raise ValueError(f"{track!r} is not an equity research track ({EQUITY_TRACKS})")


def categories_of_sector(sector: str) -> tuple:
    if sector == "technology":
        return tuple(_tech())
    if sector not in NON_TECH_SECTORS:
        raise ValueError(f"unknown sector {sector!r}")
    return NON_TECH_SECTORS[sector]


def all_categories() -> tuple:
    """Every category a classification may carry, the legacy catch-all included."""
    return tuple(_tech()) + NON_TECH_CATEGORIES + (LEGACY_UNASSIGNED,)


def track_history(classes, company_id: str, days) -> list:
    """[(day, track or None)] for each day in ``days``, from the classification as known on that day. Lets a
    report count track changes and check that none was applied before it was published."""
    return [(d, track_of(classes.category(company_id, d))) for d in days]

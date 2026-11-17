"""Source publication contracts. Declarations are not provenance authentication.

Legacy specs remain readable/hashable, but compilation and PIT ingestion require
this contract. Observation frequency is independent of strategy rebalance frequency.
"""


class AvailabilityError(ValueError):
    pass


def sources_from_spec(spec: dict) -> dict[str, dict]:
    sources = spec.get("data_sources")
    if not isinstance(sources, list) or not sources:
        raise AvailabilityError("data_sources must be a non-empty list")
    out = {}
    for src in sources:
        validate_source(src)
        name = src["name"]
        if name in out and out[name] != src:
            raise AvailabilityError("conflicting publication semantics for one source")
        out[name] = src
    return out


def validate_source(src: dict) -> None:
    def fail(message):
        raise AvailabilityError(message)

    def text(value):
        return isinstance(value, str) and bool(value.strip())

    if not isinstance(src, dict) or not text(src.get("name")):
        fail("every data source needs a name")
    if src.get("frequency") not in ("daily", "weekly", "monthly", "quarterly", "annual", "irregular"):
        fail("source frequency is required; publication_lag_days alone is unverified")
    label = src.get("period_label")
    if label not in ("observation_date", "period_start", "period_end", "publication_date"):
        fail("source period_label must distinguish observation periods from publication dates")
    if src["frequency"] in ("monthly", "quarterly", "annual") and label == "observation_date":
        fail("periodic sources require period_start, period_end or publication_date labels")
    availability = src.get("availability")
    if not isinstance(availability, dict):
        fail("explicit source availability semantics are required")
    kind = availability.get("kind")
    if kind not in ("release_dates", "release_calendar", "conservative", "daily_lag"):
        fail("unknown source availability semantics")
    if not text(availability.get("reference")) or not text(availability.get("day_mapping")):
        fail("availability requires a source reference and explicit release-to-day mapping")
    if kind == "daily_lag":
        if src["frequency"] != "daily" or label != "observation_date":
            fail("fixed publication_lag_days is supported only for daily observation dates")
        lag = src.get("publication_lag_days")
        if isinstance(lag, bool) or not isinstance(lag, int) or lag < 0:
            fail("publication_lag_days must be a whole number of days, 0 or more")
    elif "publication_lag_days" in src:
        fail("publication_lag_days conflicts with per-vintage availability semantics")
    if kind == "conservative":
        for field in ("assumption", "owner_approval", "release_history_unavailable"):
            if not text(availability.get(field)):
                fail(f"conservative availability requires documented {field}")

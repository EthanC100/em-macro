"""Independent sources: the rule an event forecast must pass before it is settled.

A resolution is accepted only with at least ``forecast_independent_sources_required`` (ledger/automation.json, 2)
sources from different organisations: different registrable domains AND different organisation names, so two pages
of the same outlet, or a syndicated copy of the same wire story, count once. Used by ``python -m ledger.resolve
settle-events`` (the forecast resolver session, docs/ledger/forecast_resolver.md).
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

MULTI_LABEL_TLDS = {"co", "com", "org", "net", "gov", "ac", "edu", "gob", "go", "or", "ne"}


def registrable_domain(url: str) -> str:
    host = (urlsplit(url).netloc or "").lower().split("@")[-1].split(":")[0]
    host = re.sub(r"^(www|m|amp|news)\.", "", host)
    parts = [p for p in host.split(".") if p]
    if len(parts) >= 3 and parts[-2] in MULTI_LABEL_TLDS and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _org_key(name: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    s = re.sub(r"\b(the|news|inc|llc|ltd|corp|corporation|company|co|group|media|press|agency)\b", " ", s)
    return " ".join(s.split())


def independent_sources(sources: list[dict], required: int) -> tuple[bool, list[dict]]:
    """Keep one source per organisation; independent when ``required`` distinct organisations
    (by registrable domain and by name) remain."""
    kept, domains, orgs = [], set(), set()
    for s in sources or []:
        url = str(s.get("url") or "").strip()
        if not re.match(r"^https?://", url):
            continue
        dom, org = registrable_domain(url), _org_key(str(s.get("organisation") or ""))
        if dom in domains or (org and org in orgs):
            continue
        domains.add(dom)
        if org:
            orgs.add(org)
        kept.append({"organisation": s.get("organisation") or dom, "url": url, "date": s.get("date") or "",
                     "quote": " ".join(str(s.get("quote") or "").split())[:300]})
    return len(kept) >= required, kept



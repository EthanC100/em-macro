"""Small, polite MediaWiki client (free public API; no key).

Wikimedia rate-limits shared IPs, so every call identifies the tool in the User-Agent,
sends maxlag, and backs off on 429/503 using Retry-After.
"""
from __future__ import annotations

import time

import requests

UA = {"User-Agent": "em-macro-election-tracker/0.1 (https://github.com/ethanc100/em-macro; observation-only research tool)"}
API = "https://{lang}.wikipedia.org/w/api.php"


def api(params: dict, lang: str = "en", tries: int = 8) -> dict:
    params = {**params, "format": "json", "formatversion": "2", "maxlag": "5"}
    last = None
    for i in range(tries):
        try:
            r = requests.get(API.format(lang=lang), params=params, headers=UA, timeout=60)
            last = r
            if r.status_code == 200:
                j = r.json()
                if "error" not in j:
                    return j
                if j["error"].get("code") != "maxlag":
                    raise RuntimeError(f"MediaWiki error: {j['error']}")
        except requests.RequestException as e:      # network blip: retry
            last = e
        wait = 5 + 6 * i
        if isinstance(last, requests.Response) and last.headers.get("retry-after", "").isdigit():
            wait = int(last.headers["retry-after"]) + 2 + 2 * i
        time.sleep(wait)
    raise RuntimeError(f"MediaWiki API failed after {tries} tries: {getattr(last, 'status_code', last)}")


def revision(title: str, before: str | None = None, lang: str = "en") -> dict | None:
    """Latest revision of `title` (following redirects), or the last one at or before the
    ISO timestamp `before`. Returns {title, revid, timestamp, wikitext} or None if missing."""
    p = {"action": "query", "prop": "revisions", "rvprop": "ids|timestamp|content", "rvslots": "main",
         "titles": title, "redirects": "1", "rvlimit": "1"}
    if before:
        p.update({"rvstart": before, "rvdir": "older"})
    page = api(p, lang)["query"]["pages"][0]
    if page.get("missing") or not page.get("revisions"):
        return None
    rv = page["revisions"][0]
    return {"title": page["title"], "revid": rv["revid"], "timestamp": rv["timestamp"],
            "wikitext": rv["slots"]["main"]["content"]}


def html(title: str, revid: int, lang: str = "en") -> str:
    """Rendered HTML of a specific revision (immutable, so snapshots are reproducible).
    Wikimedia REST endpoint first; the Action API's parse as a fallback."""
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/html/{requests.utils.quote(title.replace(' ', '_'), safe='')}/{revid}"
    for i in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code == 200 and "<table" in r.text:
                return r.text
        except requests.RequestException:
            pass
        time.sleep(5 + 5 * i)
    return api({"action": "parse", "oldid": str(revid), "prop": "text", "disabletoc": "1"}, lang)["parse"]["text"]


def permalink(title: str, revid: int, lang: str = "en") -> str:
    return f"https://{lang}.wikipedia.org/w/index.php?title={title.replace(' ', '_')}&oldid={revid}"

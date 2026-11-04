"""Event-forecast resolution through the Anthropic API with web search.

The only place in the Ledger that calls the API. The model comes from ledger/automation.json
(``anthropic_model``); the key from the ANTHROPIC_API_KEY environment variable (a repository
secret in the workflow). Without a key ``resolve_event`` returns status ``no_key`` and the
caller opens a [RESOLVE?] issue instead; nothing fails.

A resolution is accepted only when the model answers yes or no and cites at least
``forecast_independent_sources_required`` sources from different organisations (different
registrable domains and different organisation names) that state the outcome directly, judged
against the forecast's stated resolution source (for example "AP race call").
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit

SYSTEM = """You settle yes/no forecasts for a paper-trading ledger. Use the web_search tool to find out what happened.

Rules:
- Decide strictly as the stated RESOLUTION SOURCE would. "AP race call" means the Associated Press has called the race; a central-bank statement means the bank's own press release; a data release means the official publisher's figure. If that source has not reported, or reports do not settle the question, the outcome is "unresolved".
- Cite at least two independent sources from different organisations that state the outcome directly (the resolution source itself plus another organisation reporting it, or two organisations reporting the resolution source's call). Give the exact URL of each page you relied on.
- Never guess. A projection, a poll, a prediction market or an opinion piece is not a result.
- Reply with ONLY a JSON object, no prose before or after, in this shape:
{"outcome": "yes" | "no" | "unresolved", "confidence": 0.0-1.0, "summary": "one or two sentences on what settles it, with the date", "sources": [{"organisation": "Associated Press", "url": "https://...", "date": "YYYY-MM-DD", "quote": "short quote stating the outcome"}]}"""

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


def parse_answer(text: str) -> dict | None:
    """The last JSON object in the model's text."""
    if not text:
        return None
    for m in reversed(list(re.finditer(r"\{.*\}", text, re.S))):
        for cand in (m.group(0), m.group(0)[: m.group(0).rfind("}") + 1]):
            try:
                d = json.loads(cand)
                if isinstance(d, dict) and "outcome" in d:
                    return d
            except json.JSONDecodeError:
                continue
    return None


def build_prompt(question: str, resolution_date: str, resolution_source: str, country: str, today: str) -> str:
    return (f"QUESTION: {question}\n"
            f"COUNTRY: {country or 'not stated'}\n"
            f"RESOLUTION DATE: {resolution_date}\n"
            f"RESOLUTION SOURCE: {resolution_source}\n"
            f"TODAY: {today}\n\n"
            "Search for the outcome, judge it as the resolution source would, and reply with the JSON object only.")


def _api_call(prompt: str, model: str, api_key: str, config: dict) -> dict:
    """One Messages API request with the web-search server tool; returns text and usage."""
    import anthropic  # imported here so the rest of the Ledger never needs the SDK

    client = anthropic.Anthropic(api_key=api_key, timeout=float(config.get("api_timeout_seconds", 300)), max_retries=2)
    tools = [{"type": "web_search_20260209", "name": "web_search",
              "max_uses": int(config.get("api_web_search_max_uses", 8))}]
    kwargs = dict(model=model, max_tokens=int(config.get("api_max_tokens", 6000)), system=SYSTEM,
                  messages=[{"role": "user", "content": prompt}], tools=tools,
                  output_config={"effort": config.get("api_effort", "medium")})
    text, usage, searches = "", {}, 0
    for _ in range(3):   # a pause_turn means the server tool loop needs another request
        try:
            resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        except TypeError:
            resp = client.messages.create(**kwargs)
        u = getattr(resp, "usage", None)
        usage = {"input_tokens": getattr(u, "input_tokens", None), "output_tokens": getattr(u, "output_tokens", None)}
        st = getattr(getattr(u, "server_tool_use", None), "web_search_requests", None)
        searches += int(st or 0)
        for block in resp.content:
            if getattr(block, "type", "") == "text":
                text += block.text
        if resp.stop_reason == "pause_turn":
            kwargs["messages"] = kwargs["messages"] + [{"role": "assistant", "content": resp.content}]
            continue
        if resp.stop_reason == "refusal":
            det = getattr(resp, "stop_details", None)
            return {"text": text, "usage": usage, "searches": searches, "model": getattr(resp, "model", model),
                    "refusal": getattr(det, "explanation", None) or "the request was declined"}
        break
    return {"text": text, "usage": usage, "searches": searches, "model": getattr(resp, "model", model)}


def resolve_event(question: str, resolution_date: str, resolution_source: str, country: str, today: str,
                  config: dict, api_key: str | None, ask=None) -> dict:
    """Returns {"status": resolved|unresolved|no_key|error, "outcome", "summary", "sources",
    "all_sources", "usage", "searches", "model", "reason"}. ``ask`` (tests) replaces the API call
    and must return the dict ``_api_call`` returns."""
    model = config.get("anthropic_model", "claude-sonnet-5-5")
    required = int(config.get("forecast_independent_sources_required", 2))
    out = {"status": "unresolved", "outcome": None, "summary": "", "sources": [], "all_sources": [], "usage": {},
           "searches": 0, "model": model, "reason": ""}
    if not api_key and ask is None:
        out.update({"status": "no_key", "reason": "ANTHROPIC_API_KEY is not set: event forecasts are not checked automatically"})
        return out
    prompt = build_prompt(question, resolution_date, resolution_source, country, today)
    try:
        raw = (ask or (lambda p: _api_call(p, model, api_key, config)))(prompt)
    except Exception as e:  # noqa: BLE001 - the daily run must not fail on the API
        out.update({"status": "error", "reason": f"API call failed: {str(e)[:300]}"})
        return out
    out.update({"usage": raw.get("usage", {}), "searches": raw.get("searches", 0), "model": raw.get("model", model)})
    if raw.get("refusal"):
        out["reason"] = f"the model declined: {raw['refusal']}"
        return out
    ans = parse_answer(raw.get("text", ""))
    if not ans:
        out["reason"] = "the model's reply had no JSON answer"
        out["summary"] = (raw.get("text") or "")[:500]
        return out
    outcome = str(ans.get("outcome", "")).strip().lower()
    ok, kept = independent_sources(ans.get("sources") or [], required)
    out.update({"summary": " ".join(str(ans.get("summary") or "").split())[:600], "sources": kept,
                "all_sources": ans.get("sources") or [], "outcome": outcome if outcome in ("yes", "no") else None})
    if outcome not in ("yes", "no"):
        out["reason"] = "the resolution source has not settled it (model answered unresolved)"
    elif not ok:
        out["reason"] = (f"only {len(kept)} independent source{'s' if len(kept) != 1 else ''} found; "
                         f"{required} from different organisations are required")
    else:
        out["status"] = "resolved"
    return out

"""One place for Anthropic API calls made by Janus, the post-mortems and the investor letters.

The key comes from ANTHROPIC_API_KEY (a repository secret in the workflows); the model from
ledger/automation.json (``janus_model``, the current Claude Opus model). Every request streams (long runs with
web search would otherwise risk HTTP timeouts), uses adaptive thinking (always on for this model) with an
explicit effort, the server-side web search tool when asked for, and the server-side refusal fallback. The
caller gets the text, the URLs the web search returned ("sources read"), token usage and the model that served.

``KeyRejected`` is raised when the key is missing or the API rejects it (401/403): the Janus workflow stops
there instead of writing a partial run.
"""
from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "ledger/automation.json").read_text(encoding="utf-8"))
API_LOG = ROOT / "data/janus/api_log.csv"
API_LOG_COLUMNS = ["time_utc", "purpose", "ref", "model", "status", "input_tokens", "output_tokens", "web_searches",
                   "request_id"]


class KeyRejected(RuntimeError):
    """ANTHROPIC_API_KEY is missing or was rejected."""


def model_name() -> str:
    return CONFIG.get("janus_model", "claude-opus-5-5")


def call(system: str, prompt: str, *, purpose: str, ref: str = "", effort: str = "high", web_search: int = 0,
         max_tokens: int = 32000, model: str | None = None, log_path: Path | None = None) -> dict:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise KeyRejected("ANTHROPIC_API_KEY is not set")
    import anthropic

    model = model or model_name()
    client = anthropic.Anthropic(api_key=key, timeout=float(CONFIG.get("janus_timeout_seconds", 900)), max_retries=3)
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": web_search}] if web_search else []
    messages = [{"role": "user", "content": prompt}]
    text, sources, searches, usage_in, usage_out, served, req_id, status = "", [], 0, 0, 0, model, "", "ok"
    try:
        for _ in range(5):   # pause_turn: the server-side search loop wants another request
            kwargs = dict(model=model, max_tokens=max_tokens, system=system, messages=messages,
                          output_config={"effort": effort})
            if tools:
                kwargs["tools"] = tools
            with client.beta.messages.stream(betas=["server-side-fallback-2026-07-01"], fallbacks="default",
                                             **kwargs) as stream:
                resp = stream.get_final_message()
            req_id = getattr(resp, "_request_id", "") or req_id
            served = getattr(resp, "model", model)
            u = getattr(resp, "usage", None)
            usage_in += int(getattr(u, "input_tokens", 0) or 0)
            usage_out += int(getattr(u, "output_tokens", 0) or 0)
            stu = getattr(u, "server_tool_use", None)
            searches += int(getattr(stu, "web_search_requests", 0) or 0)
            for block in resp.content:
                t = getattr(block, "type", "")
                if t == "text":
                    text += block.text
                elif t == "web_search_tool_result":
                    content = getattr(block, "content", None)
                    if isinstance(content, list):
                        for item in content:
                            url = getattr(item, "url", None)
                            if url:
                                sources.append({"title": getattr(item, "title", "") or "", "url": url})
            if resp.stop_reason == "pause_turn":
                messages = messages + [{"role": "assistant", "content": resp.content}]
                continue
            if resp.stop_reason == "refusal":
                status = "refusal"
            elif resp.stop_reason == "max_tokens":
                status = "max_tokens"
            break
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
        _log(purpose, ref, model, "key rejected", 0, 0, 0, "", log_path)
        raise KeyRejected(f"the Anthropic API rejected the key: {str(e)[:200]}") from e
    seen, uniq = set(), []
    for s in sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            uniq.append(s)
    _log(purpose, ref, served, status, usage_in, usage_out, searches, req_id, log_path)
    return {"text": text, "sources_read": uniq, "searches": searches, "model": served, "status": status,
            "usage": {"input_tokens": usage_in, "output_tokens": usage_out}, "request_id": req_id,
            "time_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}


def _log(purpose, ref, model, status, tin, tout, searches, req_id, path):
    path = path or API_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=API_LOG_COLUMNS, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow({"time_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "purpose": purpose,
                    "ref": ref, "model": model, "status": status, "input_tokens": tin, "output_tokens": tout,
                    "web_searches": searches, "request_id": req_id})


def parse_json(text: str, must_have: str | None = None) -> dict | None:
    """The last JSON object in a reply (optionally one containing ``must_have``)."""
    if not text:
        return None
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    cands = [m.group(1)] if m else []
    starts = [i for i, c in enumerate(text) if c == "{"]
    end = text.rfind("}")
    cands += [text[i:end + 1] for i in starts[:50]]
    for c in cands:
        try:
            d = json.loads(c)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and (must_have is None or must_have in d):
            return d
    return None

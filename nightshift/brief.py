"""The weekly brief (Saturdays 08:00 Singapore): briefs/YYYY-MM-DD.pdf and a plain-text body for the Gmail draft.

The routine (.claude/routines/weekly-brief.md) researches the week, starting from the week's weekly review, and
writes a JSON draft; this module checks it and renders it. Checks:
* every market level carries at least two public sources from different sites, whose stated values agree
  (numbers within 0.5% of each other, or 2 basis points for levels in % or bp); a level that fails is flagged
  "(unverified)" or dropped (config/brief.yaml ``on_unverified_level``);
* no licensed data: the words in ``licensed_terms_forbidden`` (settlement, Databento, Norgate) are refused;
* paragraphs cite levels only as {id} placeholders, so no unchecked number is typed into the text by hand; any
  other digit-and-% or digit-and-bp figure in a paragraph is refused;
* the byline is plain text, "Ethan Cukierman, Horizons".

Draft JSON: {"date": "YYYY-MM-DD", "title": "...", "weekly_review": "<link or path>",
  "sections": [{"heading": "...", "paragraphs": ["... {L1} ..."]}],
  "levels": [{"id": "L1", "label": "US 10-year Treasury yield", "value": "4.12%", "as_of": "YYYY-MM-DD",
              "sources": [{"name": "...", "url": "https://...", "value": "4.12%"}, {...}]}],
  "glossary": [{"term": "...", "plain": "..."}]}

python -m nightshift.brief check --file draft.json | render --file draft.json [--out briefs/]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

from . import config as C

CFG = C.ROOT / "config/brief.yaml"
NUM = re.compile(r"-?\d+(?:,\d{3})*(?:\.\d+)?")
HAND_FIGURE = re.compile(r"\d(?:[\d.,]*)\s*(?:%|bp\b|basis points)", re.I)


def load_cfg(path: Path = CFG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _num(v: str) -> float | None:
    m = NUM.search(str(v))
    return float(m.group().replace(",", "")) if m else None


def agree(values: list[str]) -> bool:
    nums = [_num(v) for v in values]
    if any(n is None for n in nums):
        return len({str(v).strip().lower() for v in values}) == 1
    lo, hi = min(nums), max(nums)
    pct_like = all(("%" in str(v)) or ("bp" in str(v).lower()) for v in values)
    if pct_like:
        tol = 0.02 if all("%" in str(v) for v in values) else 2.0
        return hi - lo <= tol + 1e-12
    return hi - lo <= 0.005 * max(abs(hi), abs(lo), 1e-9)


def verify_level(lv: dict, min_sources: int) -> tuple[bool, str]:
    src = [s for s in lv.get("sources") or [] if str(s.get("url", "")).startswith("http")]
    hosts = {urlparse(s["url"]).netloc.lower().removeprefix("www.") for s in src}
    if len(src) < min_sources or len(hosts) < min_sources:
        return False, f"{lv.get('id')}: needs {min_sources} sources from different sites"
    if not agree([s.get("value", "") for s in src] + [lv.get("value", "")]):
        return False, f"{lv.get('id')}: sources disagree"
    return True, ""


def check(draft: dict, cfg: dict) -> dict:
    errors, notes = [], []
    text = json.dumps(draft).lower()
    for w in cfg.get("licensed_terms_forbidden") or []:
        if w.lower() in text:
            errors.append(f"licensed term '{w}' appears: the brief never uses licensed settlement data")
    levels, verified = {lv["id"]: lv for lv in draft.get("levels") or []}, {}
    for i, lv in levels.items():
        ok, why = verify_level(lv, int(cfg.get("min_sources_per_level", 2)))
        verified[i] = ok
        if not ok:
            notes.append(why)
    for s in draft.get("sections") or []:
        for p in s.get("paragraphs") or []:
            for ref in re.findall(r"\{(\w+)\}", p):
                if ref not in levels:
                    errors.append(f"paragraph cites unknown level {{{ref}}}")
            stripped = re.sub(r"\{\w+\}", "", p)
            if HAND_FIGURE.search(stripped):
                errors.append(f"hand-typed market figure in '{stripped[:60]}...': cite a checked level as {{id}}")
    if not draft.get("weekly_review"):
        errors.append("weekly_review (the week's weekly review it is built on) is required")
    return {"ok": not errors, "errors": errors, "unverified": [i for i, v in verified.items() if not v],
            "notes": notes}


def fill(p: str, levels: dict, verified_ids: set, mode: str) -> str | None:
    def rep(m):
        lv = levels[m.group(1)]
        if m.group(1) in verified_ids:
            return f"{lv['value']}"
        return f"{lv['value']} (unverified)" if mode == "flag" else "[level withheld: not confirmed by two sources]"
    out = re.sub(r"\{(\w+)\}", rep, p)
    return out


def blocks(draft: dict, cfg: dict, res: dict) -> list[tuple[str, str]]:
    """(kind, text) blocks: title, byline, date, h (heading), p (paragraph), small (sources, disclaimer)."""
    levels = {lv["id"]: lv for lv in draft.get("levels") or []}
    ok_ids = set(levels) - set(res["unverified"])
    mode = cfg.get("on_unverified_level", "flag")
    B = [("title", draft.get("title", "Horizons weekly brief")), ("byline", cfg["byline"]), ("date", draft["date"])]
    for s in draft.get("sections") or []:
        B.append(("h", s["heading"]))
        B += [("p", fill(p, levels, ok_ids, mode)) for p in s.get("paragraphs") or []]
    if draft.get("glossary"):
        B.append(("h", "Words used"))
        B += [("p", f"{g['term']}: {g['plain']}") for g in draft["glossary"]]
    B.append(("h", "Sources for every market level"))
    B += [("small", f"{lv['label']} ({lv['as_of']}): " + "; ".join(f"{s['name']} {s['url']}" for s in lv["sources"])
           + ("" if lv["id"] in ok_ids else " (unverified)"))
          for lv in levels.values() if lv["id"] in ok_ids or mode == "flag"]
    B.append(("small", "Paper portfolios only. Nothing here is investment advice."))
    return B


def to_text(draft: dict, cfg: dict, res: dict) -> str:
    out = []
    for kind, t in blocks(draft, cfg, res):
        out += ([t] if kind in ("title", "byline", "date", "small") else ["", t] if kind == "h" else [t, ""])
    return "\n".join(out) + "\n"


def render_pdf(draft: dict, cfg: dict, res: dict, out: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    ss = getSampleStyleSheet()
    style = {"title": "Title", "byline": "Italic", "date": "Normal", "h": "Heading2", "p": "BodyText", "small": "Code"}
    story = []
    for kind, t in blocks(draft, cfg, res):
        story.append(Paragraph(_x(t), ss[style[kind]] if kind != "small" else ss["BodyText"]))
        if kind in ("date", "p"):
            story.append(Spacer(1, 6))
    out.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(out), pagesize=A4, title=draft.get("title", "Horizons weekly brief"),
                      author=cfg["byline"]).build(story)


def _x(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["check", "render"])
    ap.add_argument("--file", required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    cfg, draft = load_cfg(), json.loads(Path(a.file).read_text(encoding="utf-8"))
    res = check(draft, cfg)
    print(json.dumps(res, indent=1))
    if not res["ok"] or a.cmd == "check":
        return 0 if res["ok"] else 1
    out_dir = Path(a.out) if a.out else C.ROOT / cfg.get("output_dir", "briefs")
    text = to_text(draft, cfg, res)
    (out_dir / f"{draft['date']}.txt").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{draft['date']}.txt").write_text(text, encoding="utf-8")
    render_pdf(draft, cfg, res, out_dir / f"{draft['date']}.pdf")
    print(f"written: {out_dir / (draft['date'] + '.pdf')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

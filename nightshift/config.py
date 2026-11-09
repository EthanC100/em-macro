"""Night-shift configuration (config/night.yaml) and Singapore-time helpers."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/night.yaml"
SGT = ZoneInfo("Asia/Singapore")


def load(path: Path = CONFIG) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    return cfg


def run_cap(cfg: dict) -> int:
    sm = cfg.get("safe_mode") or {}
    return int(sm.get("run_cap", 4) if sm.get("enabled") else cfg.get("run_cap", 12))


def explorer_model(cfg: dict) -> str:
    sm = cfg.get("safe_mode") or {}
    return str(sm.get("explorer_model", "sonnet")) if sm.get("enabled") else "opus"


def hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def night_of(ts: datetime) -> date:
    """The night a timestamp belongs to, named by the Singapore date on which it started: 22:30 on the 9th to
    the morning of the 10th is the night of the 9th. Anything before 12:00 Singapore time belongs to the previous
    evening's night."""
    local = ts.astimezone(SGT)
    return local.date() - timedelta(days=1) if local.time() < time(12, 0) else local.date()


def in_chain_window(ts: datetime, cfg: dict) -> bool:
    """True from window.start (22:30) to window.chain_stop (05:00), Singapore time."""
    t = ts.astimezone(SGT).time()
    start, stop = hhmm(cfg["window"]["start"]), hhmm(cfg["window"]["chain_stop"])
    return t >= start or t < stop


def in_promote_window(ts: datetime, cfg: dict) -> bool:
    t = ts.astimezone(SGT).time()
    return hhmm(cfg["window"]["promote"]) <= t < hhmm(cfg["window"]["promote_latest"])

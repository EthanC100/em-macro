"""Paths, calendar/config I/O and GitHub issue posting for the election tracker."""
from __future__ import annotations

import datetime as dt
import os

import pandas as pd
import requests
import yaml

from .rule import ROOT

DATA = ROOT / "data" / "elections"
CALENDAR = DATA / "calendar.csv"
CONFIG = DATA / "tracker.yaml"
POLLS = DATA / "polls"
SIGNALS = DATA / "signals.csv"
CHECKS = DATA / "calendar_checks.csv"
DOCS = ROOT / "docs" / "elections"
CAL_COLS = ["id", "country", "currency", "date", "type", "rounds", "status", "source_url"]
ACTIVE = ("scheduled", "due_by")


def today() -> dt.date:
    """UTC date; override with ELECTION_TRACKER_TODAY=YYYY-MM-DD for dry runs and tests."""
    o = os.environ.get("ELECTION_TRACKER_TODAY")
    return dt.date.fromisoformat(o) if o else dt.datetime.now(dt.timezone.utc).date()


def load_calendar() -> pd.DataFrame:
    cal = pd.read_csv(CALENDAR, dtype=str, keep_default_na=False)
    missing = set(CAL_COLS) - set(cal.columns)
    if missing:
        raise ValueError(f"calendar.csv is missing columns {missing}")
    return cal


def save_calendar(cal: pd.DataFrame) -> None:
    cal = cal[CAL_COLS].sort_values(["date", "id"]).reset_index(drop=True)
    cal.to_csv(CALENDAR, index=False)


def load_config() -> dict:
    with open(CONFIG) as f:
        return yaml.safe_load(f)["elections"]


def days_to(date_str: str, ref: dt.date | None = None) -> int:
    return (dt.date.fromisoformat(date_str) - (ref or today())).days


# ------------------------------------------------------------------ GitHub issues
def _gh():
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return None
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                      "X-GitHub-Api-Version": "2022-11-28"})
    return s, f"https://api.github.com/repos/{repo}"


def find_issue(title_prefix: str, label: str) -> dict | None:
    gh = _gh()
    if gh is None:
        return None
    s, base = gh
    r = s.get(f"{base}/issues", params={"labels": label, "state": "all", "per_page": 100}, timeout=30)
    r.raise_for_status()
    return next((i for i in r.json() if i["title"].startswith(title_prefix)), None)


def post_issue(title: str, body: str, label: str, dedupe_prefix: str | None = None) -> str | None:
    """Open an issue (once per `dedupe_prefix`) and return its URL.

    Without GITHUB_TOKEN/GITHUB_REPOSITORY (local runs) the issue is printed instead.
    The repository owner is @-mentioned so the GitHub mobile app notifies them.
    """
    owner = os.environ.get("ELECTION_TRACKER_NOTIFY") or os.environ.get("GITHUB_REPOSITORY_OWNER")
    if owner:
        body = f"{body}\n\ncc @{owner}"
    gh = _gh()
    if gh is None:
        print(f"[issue not posted: no GITHUB_TOKEN]\n# {title}\n{body}\n")
        return None
    existing = find_issue(dedupe_prefix or title, label)
    if existing:
        print(f"issue already exists: {existing['html_url']}")
        return existing["html_url"]
    s, base = gh
    s.post(f"{base}/labels", json={"name": label, "color": "d93f0b"}, timeout=30)   # 422 if it exists
    r = s.post(f"{base}/issues", json={"title": title, "body": body, "labels": [label]}, timeout=30)
    r.raise_for_status()
    url = r.json()["html_url"]
    print(f"issue posted: {url}")
    return url

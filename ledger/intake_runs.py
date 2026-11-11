"""Ledger intake runs: never drop an issue form (queue item Q022, approved by Ethan 2026-11-11).

ledger-intake used to share one GitHub concurrency group with ledger-daily, private-commitments and shadows-setup.
GitHub keeps at most one pending run per group and a newly queued run cancels it, so an issue form's run waiting
behind ledger-daily could be dropped silently. Now:
  * ledger-intake has its own group per issue (only a newer edit of the same issue can replace its pending run);
  * the entry is written through scripts/ledger_commit.sh on a fresh main, which re-runs the intake (and so
    re-allocates the id) when a push is rejected, so two forms racing get consecutive ids;
  * ledger-daily dispatches ledger-intake (workflow_dispatch, input ``issue``) for any open Ledger form opened by a
    person that has no comment from the Actions bot 30 minutes after it was opened or last edited (``sweep``). It
    comments on the issue first, so a form is re-run at most once per edit; intake comments on every outcome
    (logged, wrong, ledger tests failed, write failed) and logs an issue at most once (``already_logged``).

    python -m ledger.intake_runs env --issue-json ISSUE.json [--env-file "$GITHUB_ENV"]
    python -m ledger.intake_runs sweep --issues ISSUES.json [--now 2026-11-11T12:00:00Z]

``env`` reads one issue (the REST shape: the ``issue`` of an issues event, or ``gh api repos/O/R/issues/N``) and
writes ISSUE_NUMBER, ISSUE_TITLE, ISSUE_BODY, ISSUE_LABELS, ISSUE_USER, ISSUE_STATE, AUTHOR_ASSOCIATION and
LEDGER_FORM for the next steps. ``sweep`` reads the GraphQL answer of SWEEP_QUERY and prints the issue numbers to
dispatch, one per line.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

GRACE = timedelta(minutes=30)
BOT_LOGINS = ("github-actions", "github-actions[bot]")
SWEEP_QUERY = """query($owner: String!, $repo: String!) {
  repository(owner: $owner, name: $repo) {
    issues(states: OPEN, first: 100, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes { number title body createdAt lastEditedAt author { login } labels(first: 20) { nodes { name } }
              comments(last: 50) { nodes { author { login } createdAt } } } } } }"""


def is_ledger_form(title: str, body: str, labels: list[str]) -> bool:
    """Exactly the issues `python -m ledger.intake` processes (its own routing: a pasted block on an issue labelled
    ``ledger``, or a form kind from the title or a ledger:<kind> label). ledger-daily's own "[RESOLVE?]" issues
    (label ``ledger:resolve?``) are not forms."""
    from . import intake as I
    title, body = title or "", body or ""
    if "ledger" in labels and (I.paste_kind(body) or title.strip().startswith(I.PASTE_TITLE_PREFIX)):
        return True
    return I.classify(title, labels) is not None


def _labels(issue: dict) -> list[str]:
    ls = issue.get("labels") or []
    if isinstance(ls, dict):                       # GraphQL: {"nodes": [{"name": ...}]}
        ls = ls.get("nodes") or []
    return [x["name"] if isinstance(x, dict) else str(x) for x in ls]


def issue_env(issue: dict) -> dict[str, str]:
    labels = _labels(issue)
    return {"ISSUE_NUMBER": str(issue.get("number") or ""), "ISSUE_TITLE": issue.get("title") or "",
            "ISSUE_BODY": issue.get("body") or "", "ISSUE_LABELS": ",".join(labels),
            "ISSUE_USER": ((issue.get("user") or {}).get("login") or ""), "ISSUE_STATE": issue.get("state") or "",
            "AUTHOR_ASSOCIATION": issue.get("author_association") or "",
            "LEDGER_FORM": "true" if is_ledger_form(issue.get("title"), issue.get("body"), labels) else "false"}


def write_env(env: dict[str, str], path: Path) -> None:
    """Append to a GitHub Actions environment file; multi-line values use a random delimiter."""
    with path.open("a", encoding="utf-8") as f:
        for k, v in env.items():
            d = f"EOF_{secrets.token_hex(8)}"
            f.write(f"{k}<<{d}\n{v}\n{d}\n")


def _t(s) -> datetime | None:
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def needs_intake(issues, now: datetime, grace: timedelta = GRACE) -> list[int]:
    """Open Ledger forms with no intake comment (by the Actions bot) since they were opened or last edited, at least
    ``grace`` ago: their intake run was lost (dropped, or the event never delivered). ``issues`` is the GraphQL
    answer of SWEEP_QUERY, or its list of issue nodes."""
    if isinstance(issues, dict):
        issues = (((issues.get("data") or {}).get("repository") or {}).get("issues") or {}).get("nodes") or []
    out = []
    for i in issues:
        author = ((i.get("author") or {}).get("login") or "")
        if author in BOT_LOGINS or author.endswith("[bot]"):
            continue                                 # opened by a workflow (e.g. ledger-daily's [RESOLVE?] issues)
        if not is_ledger_form(i.get("title"), i.get("body"), _labels(i)):
            continue
        t0 = max(t for t in (_t(i.get("createdAt")), _t(i.get("lastEditedAt"))) if t)
        if now - t0 < grace:
            continue
        comments = (i.get("comments") or {}).get("nodes") or []
        if any(((c.get("author") or {}).get("login") or "") in BOT_LOGINS and (_t(c.get("createdAt")) or t0) >= t0
               for c in comments):
            continue
        out.append(int(i["number"]))
    return sorted(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("env")
    e.add_argument("--issue-json", required=True)
    e.add_argument("--env-file", default=None)
    s = sub.add_parser("sweep")
    s.add_argument("--issues", required=True)
    s.add_argument("--now", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "env":
        env = issue_env(json.loads(Path(a.issue_json).read_text(encoding="utf-8")))
        if a.env_file:
            write_env(env, Path(a.env_file))
        print(json.dumps({k: (v if k != "ISSUE_BODY" else f"<{len(v)} chars>") for k, v in env.items()}))
        return 0
    now = _t(a.now) if a.now else datetime.now(timezone.utc)
    for n in needs_intake(json.loads(Path(a.issues).read_text(encoding="utf-8")), now):
        print(n)
    return 0


if __name__ == "__main__":
    sys.exit(main())

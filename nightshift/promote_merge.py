"""Merge the night shift's promotion PR (dev -> main) once promote's checks and the tests workflow have passed.

Asked by Ethan on 2026-11-12: branch rules are not applied, so GitHub auto-merge is not available. The promote routine
opens (or reuses) the dev -> main PR and records its checks on dev (results/night/promote/<date>.json, with the PR);
the `promote-merge` workflow (.github/workflows/promote-merge.yml) runs this module, from MAIN's checkout, each time
the `tests` workflow completes on that PR. It merges (merge commit, pinned to the head it checked) only when all of
these hold, and otherwise merges nothing, leaves the PR open and says why in a PR comment; the morning report flags
a promotion that is not on main:

  * the PR is open, not a draft, from this repository's `dev` into `main`;
  * the tests workflow run concluded `success` on the PR's current head commit;
  * the newest promote report on that head is a `promote`-mode report with `ok: true` that names this PR;
  * the dev commit promote checked is an ancestor of the PR head, and every commit after it changed only the night
    shift's bookkeeping (results/night/, docs/agent-state.json): nothing unchecked reaches main;
  * no file the PR changes (since its merge base with main) is under a protected path of MAIN's CODEOWNERS block;
  * GitHub reports the PR mergeable (no conflicts).

The decision is a pure function of facts gathered from git and the GitHub API, so it is tested without a network.

    python -m nightshift.promote_merge decide --pr pr.json --run run.json --repo-name OWNER/REPO [--out d.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import protected as P

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = "results/night/promote"
BOOKKEEPING = ("results/night/", "docs/agent-state.json")       # what may change on dev after promote's checks
MARKER = "<!-- promote-merge -->"


def _git(repo: Path, *args) -> tuple[int, str]:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def find_report(repo: Path, head: str, pr_number: int) -> tuple[str | None, dict | None]:
    """The newest promote report on ``head`` that names PR ``pr_number`` (else the newest report), by file name."""
    rc, out = _git(repo, "ls-tree", "--name-only", f"{head}:{REPORT_DIR}")
    names = sorted((n for n in out.splitlines() if n.endswith(".json") and "_" not in n), reverse=True) if rc == 0 else []
    reports = []
    for n in names:
        rc, txt = _git(repo, "show", f"{head}:{REPORT_DIR}/{n}")
        try:
            reports.append((f"{REPORT_DIR}/{n}", json.loads(txt)))
        except (ValueError, TypeError):
            continue
    for path, r in reports:
        if _names_pr(r, pr_number):
            return path, r
    return reports[0] if reports else (None, None)


def _names_pr(report: dict, number: int) -> bool:
    pr = str(report.get("pr") or "")
    return pr.rstrip("/").endswith(f"/pull/{number}") or pr in (str(number), f"#{number}")


def gather(repo: Path, pr: dict, run: dict, repo_name: str, base: str = "origin/main") -> dict:
    """Everything decide() needs, from git (MAIN's CODEOWNERS, the PR head's tree and history) and the API answers."""
    head = ((pr.get("head") or {}).get("sha")) or ""
    facts = {"pr": pr, "run": run, "repo_name": repo_name, "report_path": None, "report": None,
             "checked_head": None, "checked_is_ancestor": False, "after_check": [], "changed": [], "protected": []}
    if not head or _git(repo, "cat-file", "-e", f"{head}^{{commit}}")[0]:
        return facts
    facts["report_path"], facts["report"] = find_report(repo, head, int(pr.get("number") or 0))
    short = (facts["report"] or {}).get("head")
    if short:
        rc, full = _git(repo, "rev-parse", "--verify", "--quiet", f"{short}^{{commit}}")
        if rc == 0:
            facts["checked_head"] = full
            facts["checked_is_ancestor"] = _git(repo, "merge-base", "--is-ancestor", full, head)[0] == 0
            if facts["checked_is_ancestor"]:
                facts["after_check"] = [p for p in _git(repo, "diff", "--name-only", f"{full}..{head}")[1].splitlines() if p]
    rc, mb = _git(repo, "merge-base", base, head)
    if rc == 0:
        facts["changed"] = [p for p in _git(repo, "diff", "--name-only", f"{mb}..{head}")[1].splitlines() if p]
    facts["protected"] = P.protected(facts["changed"], P.patterns(repo / ".github/CODEOWNERS"))
    return facts


def decide(f: dict) -> dict:
    """{"action": "merge" | "hold" | "ignore", "reasons": [...], "number", "sha"}. "ignore": not this PR's final
    state (another branch's tests, a superseded or cancelled run): no comment. "hold": merge nothing, comment why."""
    pr, run = f.get("pr") or {}, f.get("run") or {}
    number, sha = pr.get("number"), (pr.get("head") or {}).get("sha")
    out = {"action": "hold", "reasons": [], "number": number, "sha": sha}

    def done(action, *why):
        out["action"] = action
        out["reasons"] += list(why)
        return out

    if run.get("event") != "pull_request" or run.get("head_branch") != "dev":
        return done("ignore", "not a tests run of the dev -> main promotion PR")
    if not pr:
        return done("ignore", "no open pull request from dev into main")
    if pr.get("state") != "open":
        return done("ignore", f"the PR is {pr.get('state')}")
    if run.get("head_sha") != sha:
        return done("ignore", "this tests run is for an older head; the run on the current head decides")
    if run.get("conclusion") in ("cancelled", "skipped"):
        return done("ignore", f"tests run {run.get('conclusion')}")
    if (pr.get("base") or {}).get("ref") != "main" or (pr.get("head") or {}).get("ref") != "dev":
        return done("hold", "not a dev -> main PR")
    if ((pr.get("head") or {}).get("repo") or {}).get("full_name") != f.get("repo_name"):
        return done("hold", "the head branch is not this repository's dev")
    if pr.get("draft"):
        return done("hold", "the PR is a draft")
    if run.get("conclusion") != "success":
        return done("hold", f"tests workflow concluded {run.get('conclusion')} on {str(sha)[:7]}")
    rep = f.get("report")
    if not rep:
        return done("hold", f"no promote report in {REPORT_DIR}/ on the PR head")
    if rep.get("mode") != "promote":
        return done("hold", f"{f.get('report_path')} is a {rep.get('mode')!r} report, not a promote run")
    if not _names_pr(rep, int(number or 0)):
        return done("hold", f"{f.get('report_path')} does not name this PR (pr: {rep.get('pr')!r})")
    if not rep.get("ok"):
        return done("hold", "promote's checks failed: " + ("; ".join(rep.get("reasons") or []) or "see the report"))
    if not f.get("checked_head"):
        return done("hold", f"the dev commit promote checked ({rep.get('head')}) is not known")
    if not f.get("checked_is_ancestor"):
        return done("hold", f"dev was rewritten after promote checked {rep.get('head')}")
    unchecked = [p for p in f.get("after_check") or [] if not p.startswith(BOOKKEEPING)]
    if unchecked:
        return done("hold", "dev changed after promote's checks: " + ", ".join(unchecked[:10]))
    if f.get("protected"):
        return done("hold", "protected paths changed: " + ", ".join(f["protected"][:10]))
    if pr.get("mergeable") is False:
        return done("hold", "GitHub reports merge conflicts")
    if pr.get("mergeable") is None:
        return done("hold", "GitHub has not computed whether the PR is mergeable; the next tests run decides")
    return done("merge", f"promote's checks passed ({f.get('report_path')}), tests green on {str(sha)[:7]}, "
                         "only bookkeeping after the checked commit, no protected path")


def comment(d: dict) -> str:
    if d["action"] == "merge":
        return f"{MARKER}\n**promote-merge:** merging (merge commit) at {str(d['sha'])[:7]}: {d['reasons'][0]}."
    return (f"{MARKER}\n**promote-merge: not merged.** The PR stays open; the morning report flags it.\n\n"
            + "\n".join(f"- {r}" for r in d["reasons"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("decide")
    d.add_argument("--pr", required=True, help="the open dev -> main PR (GitHub API JSON), or a file with {} for none")
    d.add_argument("--run", required=True, help="the completed tests workflow run (GitHub API JSON)")
    d.add_argument("--repo-name", required=True)
    d.add_argument("--base", default="origin/main")
    d.add_argument("--out", default=None)
    d.add_argument("--comment-file", default=None)
    a = ap.parse_args(argv)
    pr = json.loads(Path(a.pr).read_text(encoding="utf-8") or "{}")
    run = json.loads(Path(a.run).read_text(encoding="utf-8"))
    res = decide(gather(ROOT, pr, run, a.repo_name, a.base) if pr else {"pr": pr, "run": run})
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    if a.comment_file:
        Path(a.comment_file).write_text(comment(res) + "\n", encoding="utf-8")
    print(json.dumps(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())

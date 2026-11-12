"""Promotion checks for the dev -> main pull request (section 5 of the brief). The promote routine opens (or reuses)
the PR and records these checks on dev, naming it; the promote-merge workflow (nightshift/promote_merge.py, main's
code) merges it only when every check passed and the tests workflow is green, otherwise it stays open and the
morning report flags it.

Checks, all on the exact tree the PR would produce (current origin/main merged with origin/dev):
  (d) the merge is conflict-free (a trial merge in a scratch worktree; conflicts are never resolved here);
  (c) no file under a protected path changed on dev since its merge base with main (.github/CODEOWNERS block);
  (a) the full test suite passes on the merged tree;
  (b) the Ledger rebuilt from scratch on main and on the merged tree, with the SAME --today and the SAME
      em-macro-data snapshot (one path, its commit recorded before and after both builds, so the 7-day settlement
      re-request cannot show as a difference), matches exactly, except for app data files that a queue item merged
      tonight lists under "ledger diff". Both audit chains must verify on the merged tree.
Build stamps (built_at, commit, the audit's checked_at, build id, the service worker's id) are ignored. Differences are reported as file
names and JSON key paths only, never values: the builds may read licensed settlements, and nothing derived from
them is printed or written by this module.

Also refused: a busy existing writer or the wrong time (nightshift.guard), unless --ignore-window (dry runs).

python -m nightshift.promote [--check-only] [--ignore-window] [--skip-tests] [--today YYYY-MM-DD]
       [--data-snapshot PATH] [--base origin/main] [--head origin/dev] [--out results/night/promote/<date>.json]
Exit 0: all checks pass (promote-merge may then merge the PR; never in --check-only mode). Exit 5: a check failed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from . import config as C
from . import guard as G
from . import protected as P
from . import queue as Q
from . import state as S

IGNORED_FILES = {"data/manifest.json", "sw.js"}
# audit.checked_at (Q026): the wall-clock second ledger/audit.py ran, copied into meta.json by ledger/build.py; a
# build stamp like built_at, so two builds a second apart never differ on it. The audit's ok, label and detail
# are still compared.
IGNORED_KEYS = {("data/meta.json", "built_at"), ("data/meta.json", "commit"), ("data/meta.json", "checked_at")}


def sh(args: list[str], cwd: Path, env=None, timeout=3600) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env, timeout=timeout)


def git(repo: Path, *args) -> str:
    r = sh(["git", *args], repo)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


# ---------------------------------------------------------------------------------------------- (d) and (c)
def trial_merge(repo: Path, base: str, head: str, wt: Path) -> dict:
    """Check out base in a scratch worktree and merge head without committing to any branch."""
    git(repo, "worktree", "add", "-q", "--detach", str(wt), base)
    env = {**os.environ, "GIT_AUTHOR_NAME": "night-shift-check", "GIT_AUTHOR_EMAIL": "night-shift@invalid",
           "GIT_COMMITTER_NAME": "night-shift-check", "GIT_COMMITTER_EMAIL": "night-shift@invalid"}
    r = sh(["git", "merge", "--no-ff", "--no-edit", "-m", "trial merge (not pushed)", head], wt, env=env)
    if r.returncode:
        conflicts = sh(["git", "diff", "--name-only", "--diff-filter=U"], wt).stdout.split()
        sh(["git", "merge", "--abort"], wt)
        return {"ok": False, "conflicts": conflicts, "detail": (r.stdout + r.stderr).strip()[-500:]}
    return {"ok": True, "conflicts": []}


def changed_on_head(repo: Path, base: str, head: str) -> list[str]:
    mb = git(repo, "merge-base", base, head)
    out = git(repo, "diff", "--name-only", f"{mb}..{head}")
    return [p for p in out.splitlines() if p]


# ---------------------------------------------------------------------------------------------- (b)
def build_ledger(tree: Path, out: Path, today: str, data_store: Path | None) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "EM_MACRO_DATA"}
    # the same snapshot for both builds; with none, neither build sees a store (and both look in an empty dir)
    env["EM_MACRO_DATA"] = str(data_store) if data_store else str(out.parent / "no-private-store")
    r = sh([sys.executable, "-m", "ledger.build", "--out", str(out), "--today", today], tree, env=env, timeout=900)
    return {"ok": r.returncode == 0, "detail": (r.stderr or r.stdout).strip()[-400:] if r.returncode else ""}


def _norm(rel: str, obj):
    if isinstance(obj, dict):
        return {k: _norm(rel, v) for k, v in obj.items() if (rel, k) not in IGNORED_KEYS}
    if isinstance(obj, list):
        return [_norm(rel, v) for v in obj]
    return obj


def _paths(a, b, prefix="", out=None, limit=20):
    out = [] if out is None else out
    if len(out) >= limit:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{prefix}.{k}" + (" (added)" if k not in a else " (removed)"))
            elif a[k] != b[k]:
                _paths(a[k], b[k], f"{prefix}.{k}", out, limit)
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                _paths(x, y, f"{prefix}[{i}]", out, limit)
    else:
        out.append(prefix or "(whole file)")
    return out


def compare_builds(a: Path, b: Path) -> list[dict]:
    """Files that differ between two Ledger builds, with up to 20 JSON key paths each (never values)."""
    fa = {p.relative_to(a).as_posix() for p in a.rglob("*") if p.is_file()}
    fb = {p.relative_to(b).as_posix() for p in b.rglob("*") if p.is_file()}
    diffs = []
    for rel in sorted(fa | fb):
        if rel in IGNORED_FILES:
            continue
        if rel not in fa or rel not in fb:
            diffs.append({"file": rel, "paths": ["(added)" if rel not in fa else "(removed)"]})
            continue
        xa, xb = (a / rel).read_bytes(), (b / rel).read_bytes()
        if xa == xb:
            continue
        if rel.endswith(".json"):
            ja, jb = _norm(rel, json.loads(xa)), _norm(rel, json.loads(xb))
            if ja == jb:
                continue
            diffs.append({"file": rel, "paths": _paths(ja, jb)})
        else:
            diffs.append({"file": rel, "paths": ["(content)"]})
    return diffs


def merged_item_ids(repo: Path, base: str, head: str) -> list[str]:
    """Queue items merged into dev since base: only pr-review's merge commits ("Merge Qnnn: ..."), never ids that
    merely appear in bookkeeping messages, so an unmerged item's declared Ledger diff can never excuse a difference."""
    subjects = git(repo, "log", "--format=%s", f"{base}..{head}").splitlines()
    return sorted({m.group(1) for s in subjects for m in [re.match(r"^Merge (Q\d{3,})\b", s)] if m})


def unexplained(diffs: list[dict], intended: set[str]) -> list[dict]:
    ok = {f if "/" in f else f"data/{f}" for f in intended}
    return [d for d in diffs if d["file"] not in ok]


def store_head(store: Path | None) -> str | None:
    if not store or not (store / ".git").exists():
        return None
    r = sh(["git", "rev-parse", "HEAD"], store)
    return r.stdout.strip() if r.returncode == 0 else None


# ---------------------------------------------------------------------------------------------- run
def run(repo: Path, base: str, head: str, today: str, data_store: Path | None, run_tests: bool = True,
        work: Path | None = None) -> dict:
    work = Path(tempfile.mkdtemp(prefix="promote-", dir=work))
    res = {"base": git(repo, "rev-parse", "--short", base), "head": git(repo, "rev-parse", "--short", head),
           "today": today, "checks": {}, "ok": False}
    wt_main, wt_merge = work / "main", work / "merged"
    try:
        ahead = git(repo, "rev-list", "--count", f"{base}..{head}")
        res["dev_commits_ahead"] = int(ahead)
        if int(ahead) == 0:
            res["checks"]["nothing"] = {"ok": False, "detail": "dev has no commits that main lacks"}
            return res
        m = trial_merge(repo, base, head, wt_merge)
        res["checks"]["d_conflict_free"] = m
        changed = changed_on_head(repo, base, head)
        prot = P.protected(changed, P.patterns(repo / ".github/CODEOWNERS"))
        res["checks"]["c_protected_paths"] = {"ok": not prot, "touched": prot, "n_changed": len(changed)}
        if not m["ok"]:
            return res
        if run_tests:
            t = sh([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], wt_merge,
                   env={**os.environ, "NIGHT_SHIFT_STRICT": "1"}, timeout=3600)
            tail = t.stdout.strip().splitlines()[-1:] if t.stdout.strip() else []
            res["checks"]["a_tests"] = {"ok": t.returncode == 0, "summary": tail[0] if tail else t.stderr[-300:]}
        else:
            res["checks"]["a_tests"] = {"ok": False, "skipped": True, "summary": "not run (--skip-tests)"}
        git(repo, "worktree", "add", "-q", "--detach", str(wt_main), base)
        snap_before = store_head(data_store)
        b1 = build_ledger(wt_main, work / "app-main", today, data_store)
        b2 = build_ledger(wt_merge, work / "app-merged", today, data_store)
        snap_after = store_head(data_store)
        same_snapshot = snap_before == snap_after
        ids = merged_item_ids(repo, base, head)
        items = Q.parse((wt_merge / "docs/queue.md").read_text(encoding="utf-8")) \
            if (wt_merge / "docs/queue.md").exists() else []
        intended = Q.intended_ledger_files(items, ids)
        diffs = compare_builds(work / "app-main", work / "app-merged") if b1["ok"] and b2["ok"] else []
        bad = unexplained(diffs, intended)
        audit = [sh([sys.executable, "-m", mod, "verify"], wt_merge) for mod in ("ledger.audit", "ledger.janus")]
        res["checks"]["b_ledger_rebuild"] = {
            "ok": b1["ok"] and b2["ok"] and same_snapshot and not bad and all(a.returncode == 0 for a in audit),
            "built": {"main": b1, "merged": b2}, "snapshot": snap_before or "none (no private store)",
            "same_snapshot": same_snapshot, "items_merged": ids, "intended_files": sorted(intended),
            "differences": diffs, "unexplained": [d["file"] for d in bad],
            "audit_verify": [a.returncode == 0 for a in audit]}
        res["ok"] = all(c.get("ok") for c in res["checks"].values())
        return res
    finally:
        for wt in (wt_main, wt_merge):
            if wt.exists():
                sh(["git", "worktree", "remove", "--force", str(wt)], repo)
        shutil.rmtree(work, ignore_errors=True)


def reasons(res: dict) -> list[str]:
    out = []
    names = {"nothing": "nothing to promote", "d_conflict_free": "(d) merge conflicts",
             "c_protected_paths": "(c) protected paths touched", "a_tests": "(a) test suite",
             "b_ledger_rebuild": "(b) Ledger rebuild differs", "window": "time or busy writer",
             "config": "main's config/night.yaml unreadable (fail safe)"}
    for k, v in res.get("checks", {}).items():
        if not v.get("ok"):
            extra = v.get("touched") or v.get("conflicts") or v.get("unexplained") or v.get("reasons") \
                or v.get("summary") or v.get("detail") or ""
            out.append(f"{names.get(k, k)}: {extra}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--ignore-window", action="store_true")
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--today", default=None)
    ap.add_argument("--data-snapshot", default=None)
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--head", default="origin/dev")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    now, repo = C.now_utc(), C.ROOT
    today = a.today or now.astimezone(C.SGT).date().isoformat()
    try:
        cfg = C.load_main(repo)                 # main's config, fetched now: never dev's copy
    except C.MainConfigError as e:
        cfg = None
        res = {"ok": False, "today": today, "checks": {"config": {"ok": False, "reasons": [str(e)]}}}
    store = Path(a.data_snapshot) if a.data_snapshot else (
        Path(os.environ["EM_MACRO_DATA"]) if os.environ.get("EM_MACRO_DATA") else
        (repo.parent / "em-macro-data" if (repo.parent / "em-macro-data").is_dir() else None))
    if cfg is not None:
        res = {"checks": {}}
    if cfg is not None and not a.ignore_window:
        g = G.check("promote", now, cfg, S.load(), G.busy_runs(cfg))
        if not g["go"]:
            res = {"ok": False, "today": today, "checks": {"window": {"ok": False, "reasons": g["reasons"]}}}
    if not res["checks"]:
        res = run(repo, a.base, a.head, today, store, run_tests=not a.skip_tests)
    res["mode"] = "check only" if a.check_only else "promote"
    res["reasons"] = reasons(res)
    out = Path(a.out) if a.out else repo / f"results/night/promote/{today}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"ok": res["ok"], "mode": res["mode"], "reasons": res["reasons"], "written": str(out)}, indent=1))
    return 0 if res["ok"] else 5


if __name__ == "__main__":
    sys.exit(main())

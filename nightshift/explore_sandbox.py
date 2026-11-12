"""Q019: the explorer's sandbox: a plain directory (no ``.git``) holding only an allowlist of files from dev, with no
``data/`` or ``results/`` directory anywhere, and a bundle (``.explore/``) of main's verified extract. The explorer
works only there; the routine collects what it wrote afterwards. Protected on main with the loader.

Why a copy and not a sparse checkout or a worktree: a worktree or a sparse checkout keeps the whole object database,
so ``git show origin/main:data/...`` would still print 2020+ rows. The sandbox has no git objects at all, and it is an
allowlist rather than "everything except data/ and results/" because 2020+ figures also sit outside those two
directories (trials.csv results, docs/prereg/ and README performance tables, tests/fixtures/live/ copies of live
files). What the explorer needs to avoid repeating a trial comes as ``.explore/tested_trials.csv``: trial id, name,
hypothesis and design sample only, never results or decisions.

  python -m nightshift.explore_sandbox create --dest DIR [--ref origin/dev]   # exit 0 made, 4 gate closed, 1 refused
  python -m nightshift.explore_sandbox collect --sandbox DIR                   # after the explorer: exit 0, 1 refused rows

``create`` (run by the night-explorer routine from its own checkout, before the explorer starts): applies the gate
(``explore_data.explorer_gate``: main's manifest, CODEOWNERS block, sandboxed routine), reads main's cutoff and
manifest fresh, fetches the extract from the private store and checks its sha256 (no other store file touches disk),
then writes the allowlisted files of ``--ref`` (fetched fresh) and the bundle:
``.explore/sandbox.json`` (cutoff, hashes, commits, file inventory), ``manifest.json``, ``extract.csv``,
``tested_trials.csv``, ``exploration_log.csv`` (dev's variant log; every row ends on or before the cutoff) and
``out/`` for the explorer's outputs. It ends by checking the tree: no ``data``/``results``/``.git``/``fixtures``
directory, no symbolic link, nothing outside the allowlist.

``collect`` (run by the routine from its own checkout after the explorer returns): re-logs every variant from
``.explore/out/variants.csv`` through ``nightshift.logs.log_variant`` (main's cutoff, fetched fresh; refused rows are
reported and the exit is 1), and copies back only new or changed files under the write prefixes: ``lab/sleeves/``,
``docs/prereg_drafts/`` and ``.explore/out/exploration/`` (to ``results/exploration/``). Nothing else leaves the
sandbox.

The sandbox closes the paths the explorer could reach by reading files. It does not close the network or the routine's
own checkout reached by absolute path: those need the routine-level isolation drafted in docs/exploration_data.md.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath

from . import config as C
from . import explore_data as ED
from . import logs as LG

# Files copied from the ref (exact files, or directories ending in "/"). Nothing else enters the sandbox.
ALLOW = ("CLAUDE.md", "requirements.txt", ".claude/agents/explorer.md", "nightshift/", "lab/", "docs/prereg_drafts/")
# Refused anywhere in a path, even under an allowed directory.
DENY_PARTS = {"data", "results", "fixtures", ".git", ED.BUNDLE}   # a ref can never plant a bundle
# Where the explorer may write things the routine collects (sandbox path -> checkout path).
WRITE = {"lab/sleeves/": "lab/sleeves/", "docs/prereg_drafts/": "docs/prereg_drafts/",
         f"{ED.BUNDLE}/out/exploration/": "results/exploration/"}
TRIAL_COLS = ("trial_id", "name", "hypothesis", "design_sample")   # never result, decision, test_sample or notes
MAX_COLLECT_BYTES = 2_000_000
DEV_REF = "origin/dev"


class Refused(ED.Refused):
    pass


def _allowed(rel: str) -> bool:
    parts = PurePosixPath(rel).parts
    if not parts or any(p in DENY_PARTS for p in parts) or ".." in parts:
        return False
    return any(rel == a or (a.endswith("/") and rel.startswith(a)) for a in ALLOW)


def _fetch_ref(repo: Path, ref: str) -> str:
    if ref.startswith(f"{ED.REMOTE}/"):
        br = ref.split("/", 1)[1]
        f = ED._git(repo, "fetch", "-q", ED.REMOTE, f"+refs/heads/{br}:refs/remotes/{ED.REMOTE}/{br}")
        if f.returncode != 0:
            raise Refused(f"git fetch {ref} failed: {f.stderr.decode(errors='replace').strip()[-200:]}")
    r = ED._git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
    if r.returncode != 0:
        raise Refused(f"{ref} is not a commit")
    return r.stdout.decode().strip()


def _tree(repo: Path, commit: str) -> list[tuple[str, str, str]]:
    r = ED._git(repo, "ls-tree", "-r", "-z", "--full-tree", commit)
    if r.returncode != 0:
        raise Refused(f"cannot list {commit}")
    out = []
    for ent in r.stdout.split(b"\0"):
        if not ent:
            continue
        meta, path = ent.split(b"\t", 1)
        mode, typ, oid = meta.decode().split()
        out.append((mode, oid, path.decode("utf-8")))
    return out


def _redacted_trials(raw: bytes | None) -> bytes:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(TRIAL_COLS)
    if raw:
        for r in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
            w.writerow([r.get(c, "") for c in TRIAL_COLS])
    return out.getvalue().encode("utf-8")


def _checked_log(raw: bytes | None, cutoff: date) -> bytes:
    if raw is None:
        return (",".join(LG.EXP_COLS) + "\n").encode()
    for n, r in enumerate(csv.DictReader(io.StringIO(raw.decode("utf-8"))), start=2):
        try:
            end = date.fromisoformat(r["data_end"])
        except (KeyError, TypeError, ValueError) as e:
            raise Refused(f"results/exploration/log.csv line {n}: unreadable data_end") from e
        if end > cutoff:
            raise Refused(f"results/exploration/log.csv line {n} ends {end}, after main's cutoff {cutoff}: the log "
                          "is not copied into a sandbox")
    return raw


def audit(dest: Path) -> list[str]:
    """What is wrong with a sandbox tree (empty = clean)."""
    bad = []
    if (dest / ".git").exists():
        bad.append(".git present")
    for p in sorted(dest.rglob("*")):
        rel = p.relative_to(dest).as_posix()
        if p.is_symlink():
            bad.append(f"symbolic link: {rel}")
            continue
        parts = PurePosixPath(rel).parts
        if parts[0] == ED.BUNDLE:
            if any(x in {"data", "results", ".git"} for x in parts[1:]):
                bad.append(f"forbidden directory in the bundle: {rel}")
            continue
        if any(x in DENY_PARTS for x in parts):
            bad.append(f"forbidden path: {rel}")
        elif p.is_file() and not _allowed(rel):
            bad.append(f"not on the allowlist: {rel}")
    return bad


def create(dest: Path, repo=None, ref: str = DEV_REF) -> dict:
    repo = ED._repo(repo)
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise Refused(f"{dest} exists and is not empty")
    if dest.resolve().is_relative_to(repo.resolve()):
        raise Refused("the sandbox must be outside the checkout")
    up = next((p for p in [dest.resolve(), *dest.resolve().parents] if p.exists()), None)
    if up is not None and ED._git(up, "rev-parse", "--is-inside-work-tree").returncode == 0:
        raise Refused(f"{dest} is inside a git work tree: git there would reach that repository's objects")
    gate = ED.explorer_gate(repo)
    if gate:
        raise Refused("explorer gate closed: " + "; ".join(gate))
    cutoff = ED._cutoff()
    man, mb = ED._main_manifest(repo, cutoff)
    eb = ED.store_extract(man["extract"])
    ED.parse_extract(eb, [str(s["id"]) for s in man["extract"]["series"]], cutoff)
    main_commit = ED._git(repo, "rev-parse", f"{ED.REMOTE}/{ED.BRANCH}").stdout.decode().strip()
    commit = _fetch_ref(repo, ref)
    trials = _redacted_trials(ED._show_main(repo, "trials.csv"))
    log = ED._git(repo, "show", f"{commit}:results/exploration/log.csv")
    logb = _checked_log(log.stdout if log.returncode == 0 else None, cutoff)
    dest.mkdir(parents=True, exist_ok=True)
    files, skipped = {}, []
    try:
        for mode, oid, rel in _tree(repo, commit):
            if not _allowed(rel):
                continue
            if mode not in ("100644", "100755"):
                skipped.append(f"{rel} (mode {mode}: links and submodules never enter the sandbox)")
                continue
            b = ED._git(repo, "cat-file", "blob", oid)
            if b.returncode != 0:
                raise Refused(f"{rel}: unreadable blob")
            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b.stdout)
            if mode == "100755":
                out.chmod(0o755)
            files[rel] = ED._sha(b.stdout)
        bd = dest / ED.BUNDLE
        (bd / "out/exploration").mkdir(parents=True, exist_ok=True)
        (bd / "manifest.json").write_bytes(mb)
        (bd / "extract.csv").write_bytes(eb)
        (bd / "tested_trials.csv").write_bytes(trials)
        (bd / "exploration_log.csv").write_bytes(logb)
        meta = {"schema": 1, "cutoff": cutoff.isoformat(), "manifest_sha256": ED._sha(mb),
                "extract_sha256": ED._sha(eb), "main_commit": main_commit, "ref": ref, "ref_commit": commit,
                "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "explorer": {"max_hypotheses_per_night": None}, "write": WRITE, "files": files}
        try:
            meta["explorer"] = dict(C.load_main().get("explorer") or {})
        except Exception:  # noqa: BLE001 - informational only; the cutoff above is what binds
            pass
        (bd / "sandbox.json").write_text(json.dumps(meta, indent=1, default=str) + "\n", encoding="utf-8")
        bad = audit(dest)
        if bad:
            raise Refused("the sandbox failed its own audit: " + "; ".join(bad[:10]))
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    return {"sandbox": str(dest), "cutoff": meta["cutoff"], "ref_commit": commit, "main_commit": main_commit,
            "files": len(files), "skipped": skipped, "extract_sha256": meta["extract_sha256"]}


def collect(sandbox: Path, repo=None, log_path: Path | None = None) -> dict:
    repo = ED._repo(repo)
    sandbox = Path(sandbox)
    if not ED.in_sandbox(sandbox):
        raise Refused(f"{sandbox} is not a sandbox (no {ED.BUNDLE}/sandbox.json, or it has a .git)")
    meta = json.loads((sandbox / ED.BUNDLE / "sandbox.json").read_text(encoding="utf-8"))
    logged, refused, copied = [], [], []
    vp = sandbox / ED.BUNDLE / "out/variants.csv"
    if vp.is_file() and not vp.is_symlink():
        with vp.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                row = {k: (r.get(k) or "") for k in LG.EXP_COLS if k != "logged_on"}
                try:
                    LG.log_variant(row, path=log_path)        # main's cutoff, fetched fresh; the real log
                    logged.append(row["variant_id"])
                except (LG.CutoffUnreadable, ValueError, KeyError) as e:
                    refused.append(f"{row.get('variant_id')}: {e}")
    known = meta.get("files") or {}
    for src_prefix, dst_prefix in WRITE.items():
        base = sandbox / src_prefix
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(sandbox).as_posix()
            if p.is_symlink():
                refused.append(f"{rel}: symbolic link not collected")
                continue
            if not p.is_file():
                continue
            b = p.read_bytes()
            if known.get(rel) == ED._sha(b):
                continue                                       # unchanged from dev
            if len(b) > MAX_COLLECT_BYTES:
                refused.append(f"{rel}: {len(b)} bytes, over {MAX_COLLECT_BYTES} (aggregate tables only)")
                continue
            out_rel = dst_prefix + rel[len(src_prefix):]
            if any(x in {"..", ".git"} for x in PurePosixPath(out_rel).parts):
                refused.append(f"{rel}: bad destination")
                continue
            out = repo / out_rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b)
            copied.append(out_rel)
    return {"variants_logged": logged, "refused": refused, "copied": copied}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--dest", required=True)
    c.add_argument("--ref", default=DEV_REF)
    k = sub.add_parser("collect")
    k.add_argument("--sandbox", required=True)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "create":
            r = create(Path(a.dest), ref=a.ref)
        else:
            r = collect(Path(a.sandbox))
    except Refused as e:
        print(f"refused: {e}")
        return 4 if "gate closed" in str(e) else 1
    except ED.Refused as e:
        print(f"refused: {e}")
        return 1
    print(json.dumps(r, indent=1))
    return 1 if r.get("refused") else 0


if __name__ == "__main__":
    sys.exit(main())

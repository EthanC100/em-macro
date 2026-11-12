"""Q019: the explorer's sandbox: a plain directory (no ``.git``) holding only an allowlist of files from dev, with no
``data/`` or ``results/`` directory anywhere, and a bundle (``.explore/``) of main's verified extract. The explorer
works only there; the routine collects what it wrote afterwards. Protected on main with the loader.

Why a copy and not a sparse checkout or a worktree: a worktree or a sparse checkout keeps the whole object database,
so ``git show origin/main:data/...`` would still print 2020+ rows. The sandbox has no git objects at all, and it is an
allowlist rather than "everything except data/ and results/" because 2020+ figures also sit outside those two
directories (trials.csv results, docs/prereg/ and README performance tables, tests/fixtures/live/ copies of live
files). What the explorer needs to avoid repeating a trial comes as ``.explore/tested_trials.csv``: trial id, name,
hypothesis and design sample only, never results or decisions.

  python -m nightshift.explore_sandbox [--repo CHECKOUT] create --dest DIR [--ref origin/dev]  # 0 made, 4 gate, 1 refused
  python -m nightshift.explore_sandbox [--repo CHECKOUT] collect --sandbox DIR [--into CHECKOUT]  # 0, or 1 refused

The routine runs both from main's ``nightshift/`` extracted outside every checkout (``git archive``, ``python -I``,
``--repo`` the checkout): this module imports unprotected ones (config, protected), so dev's copy is not trusted.

``create`` (run by the night-explorer routine from its own checkout, before the explorer starts): applies the gate
(``explore_data.explorer_gate``: main's manifest, CODEOWNERS block, sandboxed routine), reads main's cutoff and
manifest fresh, fetches the extract from the private store and checks its sha256 (no other store file touches disk),
then writes the allowlisted files (code and rules from origin/main: ``CLAUDE.md``, ``requirements.txt``,
``.claude/agents/explorer.md``, ``nightshift/``; the night's outputs so far from ``--ref``, fetched fresh: ``lab/``,
``docs/prereg_drafts/``) and the bundle:
``.explore/sandbox.json`` (cutoff, hashes, commits, file inventory), ``manifest.json``, ``extract.csv``,
``tested_trials.csv``, ``exploration_log.csv`` (dev's variant log; every row ends on or before the cutoff) and
``out/`` for the explorer's outputs. It ends by checking the tree: no ``data``/``results``/``.git``/``fixtures``
directory, no symbolic link, nothing outside the allowlist.

``collect`` (run by the routine after the explorer returns; ``--into`` the checkout to write, default this code's
own): re-logs every variant from ``.explore/out/variants.csv`` through ``nightshift.logs.log_variant`` (main's cutoff,
fetched fresh; refused rows are reported and the exit is 1), and copies back only new or changed files under the
write prefixes: ``lab/sleeves/`` (20 kB each), ``docs/prereg_drafts/`` (200 kB) and ``.explore/out/exploration/`` (to
``results/exploration/``, 2 MB). Each must be UTF-8 text inside the sandbox with no symbolic link on its way (a linked
folder could reach the private store), and a table must carry no day or month stamp after main's cutoff. Nothing else
leaves the sandbox.

The sandbox closes the paths the explorer could reach by reading files. It does not close the network or the routine's
own checkout reached by absolute path: those need the routine-level isolation drafted in docs/exploration_data.md.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath

from . import config as C
from . import explore_data as ED
from . import logs as LG

# Files copied into the sandbox (exact files, or directories ending in "/"). Nothing else enters it. Code and rules
# come from origin/main (Ethan's reviewed copies, whatever dev holds); the night's own outputs so far come from the ref.
FROM_MAIN = ("CLAUDE.md", "requirements.txt", ".claude/agents/explorer.md", "nightshift/", "lab/__init__.py",
             "lab/book.py", "lab/sleeves/README.md", "docs/prereg_drafts/README.md")
FROM_REF = ("lab/sleeves/", "docs/prereg_drafts/")
ALLOW = FROM_MAIN + FROM_REF
# The ref's files: only these exact shapes (no subfolders), each screened like a collected file (_screen).
REF_FILE = re.compile(r"^(lab/sleeves/[A-Za-z0-9_.-]+\.yaml|docs/prereg_drafts/[A-Za-z0-9_.-]+\.md)$")
# Refused anywhere in a path, even under an allowed directory.
DENY_PARTS = {"data", "results", "fixtures", ".git", ED.BUNDLE}   # a ref can never plant a bundle
# Where the explorer may write things the routine collects (sandbox path -> checkout path).
WRITE = {"lab/sleeves/": "lab/sleeves/", "docs/prereg_drafts/": "docs/prereg_drafts/",
         f"{ED.BUNDLE}/out/exploration/": "results/exploration/"}
# Trial id and name only: the hypothesis text can carry outcomes ("the failed T01"); never result, decision or notes.
TRIAL_COLS = ("trial_id", "name")
# dev's variant log in the sandbox: no params, code_ref or notes (free text); a description with a post-cutoff stamp is
# replaced.
LOG_COLS = ("logged_on", "hypothesis_id", "variant_id", "description", "data_start", "data_end", "n_obs", "metric",
            "value", "nominated")
KIND = {"lab/sleeves/": "sleeve", "docs/prereg_drafts/": "draft", f"{ED.BUNDLE}/out/exploration/": "table"}
MAX_BYTES = {"sleeve": 20_000, "draft": 200_000, "table": 2_000_000}
SECRET_ENV = re.compile(r"TOKEN|KEY|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|COOKIE|FIRE_URL", re.I)
# In collected tables: a day or month stamp after the cutoff means row-level post-cutoff data, which is refused.
STAMP = re.compile(r"(?<![0-9])((?:19|20)[0-9]{2}-(?:0[1-9]|1[0-2]))(?:-(0[1-9]|[12][0-9]|3[01]))?(?![0-9])")
DEV_REF = "origin/dev"


class Refused(ED.Refused):
    pass


def _allowed(rel: str, allow: tuple[str, ...] = ALLOW) -> bool:
    parts = PurePosixPath(rel).parts
    if not parts or any(p in DENY_PARTS for p in parts) or ".." in parts:
        return False
    return any(rel == a or (a.endswith("/") and rel.startswith(a)) for a in allow)


def _late_stamps(text: str, cutoff: date, months: bool = True) -> list[str]:
    cut = cutoff.isoformat()
    return sorted({m.group(0) for m in STAMP.finditer(text)
                   if (m.group(0) > cut if m.group(2) else months and m.group(1) > cut[:7])})


def _secrets_in(text: str) -> list[str]:
    """Names (never values) of credential-like environment variables whose value appears in the text."""
    return sorted(k for k, v in os.environ.items() if SECRET_ENV.search(k) and len(v) >= 8 and v in text)


def _screen(kind: str, b: bytes, cutoff: date) -> str | None:
    """Why a file may not cross the sandbox boundary (either way), or None. Tables: no day or month stamp after the
    cutoff; drafts: no day stamp (a test window like 2020-01..2026-09 is planning text); sleeves: none outside their
    launched / retire_on lines. Every kind: a size cap, UTF-8 text, and no credential value from the environment."""
    if len(b) > MAX_BYTES[kind]:
        return f"{len(b)} bytes, over the {kind} cap of {MAX_BYTES[kind]}"
    try:
        text = b.decode("utf-8")
    except UnicodeDecodeError:
        return "not UTF-8 text"
    body = text
    if kind == "sleeve":
        body = "\n".join(x for x in text.splitlines() if not re.match(r"\s*(launched|retire_on)\s*:", x))
    late = _late_stamps(body, cutoff, months=kind != "draft")
    if late:
        return f"dated after the cutoff {cutoff} ({', '.join(late[:3])}): row-level post-cutoff data never crosses"
    sec = _secrets_in(text)
    if sec:
        return f"contains the value of {', '.join(sec)}"
    return None


def _inside(p: Path, root: Path) -> bool:
    """p is under root with no symbolic link on the way (a linked directory would reach outside the sandbox)."""
    try:
        rel = p.relative_to(root)
    except ValueError:
        return False
    q = root
    for part in rel.parts:
        q = q / part
        if q.is_symlink():
            return False
    return p.resolve().is_relative_to(root.resolve())


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


def _kind(rel: str) -> str:
    return next(k for pre, k in KIND.items() if rel.startswith(pre))


def _redacted_trials(raw: bytes | None) -> bytes:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(TRIAL_COLS)
    if raw:
        for r in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
            w.writerow([r.get(c, "") for c in TRIAL_COLS])
    return out.getvalue().encode("utf-8")


def _checked_log(raw: bytes | None, cutoff: date) -> bytes:
    """dev's variant log for the sandbox: LOG_COLS only; every row must end by the cutoff (else refused); a
    description carrying a post-cutoff stamp is replaced."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(LOG_COLS)
    if raw is None:
        return out.getvalue().encode()
    for n, r in enumerate(csv.DictReader(io.StringIO(raw.decode("utf-8"))), start=2):
        try:
            end = date.fromisoformat(r["data_end"])
        except (KeyError, TypeError, ValueError) as e:
            raise Refused(f"results/exploration/log.csv line {n}: unreadable data_end") from e
        if end > cutoff:
            raise Refused(f"results/exploration/log.csv line {n} ends {end}, after main's cutoff {cutoff}: the log "
                          "is not copied into a sandbox")
        row = {c: r.get(c, "") or "" for c in LOG_COLS}
        if _late_stamps(" ".join(row.values()), cutoff):
            row["description"] = "[withheld: dated after the cutoff]"
        w.writerow([row[c] for c in LOG_COLS])
    return out.getvalue().encode()


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
    entries = ([(*e, False) for e in _tree(repo, main_commit) if _allowed(e[2], FROM_MAIN)]
               + [(*e, True) for e in _tree(repo, commit) if _allowed(e[2], FROM_REF) and not _allowed(e[2], FROM_MAIN)])
    try:
        for mode, oid, rel, from_ref in entries:
            if from_ref and not REF_FILE.match(rel):
                skipped.append(f"{rel} (only lab/sleeves/*.yaml and docs/prereg_drafts/*.md come from the ref)")
                continue
            if mode not in ("100644", "100755"):
                skipped.append(f"{rel} (mode {mode}: links and submodules never enter the sandbox)")
                continue
            b = ED._git(repo, "cat-file", "blob", oid)
            if b.returncode != 0:
                raise Refused(f"{rel}: unreadable blob")
            why = _screen(_kind(rel), b.stdout, cutoff) if from_ref else None
            if why:
                skipped.append(f"{rel} ({why})")
                continue
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
    """Bring the explorer's outputs into the checkout ``repo``: variants re-logged against main's cutoff, and new or
    changed files under the write prefixes, each inside the sandbox with no link on its way, UTF-8 text, under its
    size cap, and (tables) with no day or month stamp after the cutoff."""
    repo = ED._repo(repo)
    sandbox = Path(sandbox)
    if not ED.in_sandbox(sandbox):
        raise Refused(f"{sandbox} is not a sandbox (no {ED.BUNDLE}/sandbox.json, or it has a .git)")
    cutoff = ED._cutoff()                                     # main's, fetched fresh: never the sandbox's copy
    meta = json.loads((sandbox / ED.BUNDLE / "sandbox.json").read_text(encoding="utf-8"))
    logged, refused, copied = [], [], []
    vp = sandbox / ED.BUNDLE / "out/variants.csv"
    if vp.exists() and not (_inside(vp, sandbox) and vp.is_file()):
        refused.append(f"{ED.BUNDLE}/out/variants.csv: not a plain file inside the sandbox; no variant collected")
    elif vp.is_file():
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
        if base.exists() and not _inside(base, sandbox):
            refused.append(f"{src_prefix}: a symbolic link on the way; nothing collected from it")
            continue
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(sandbox).as_posix()
            if p.is_symlink() or not _inside(p, sandbox):
                refused.append(f"{rel}: symbolic link not collected")
                continue
            if not p.is_file():
                continue
            b = p.read_bytes()
            if known.get(rel) == ED._sha(b):
                continue                                       # unchanged from what create put there
            kind = KIND[src_prefix]
            if kind == "table" and "/" not in rel[len(src_prefix):]:
                refused.append(f"{rel}: tables go in a hypothesis folder (never over results/exploration/log.csv)")
                continue
            if kind != "table" and not REF_FILE.match(rel):
                refused.append(f"{rel}: only lab/sleeves/*.yaml and docs/prereg_drafts/*.md are collected")
                continue
            why = _screen(kind, b, cutoff)
            if why:
                refused.append(f"{rel}: {why}")
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
    ap.add_argument("--repo", default=None, help="the checkout whose git and remotes to use (run main's code from "
                    "outside it: see docs/exploration_data.md); default: this code's own checkout")
    c = sub.add_parser("create")
    c.add_argument("--dest", required=True)
    c.add_argument("--ref", default=DEV_REF)
    k = sub.add_parser("collect")
    k.add_argument("--sandbox", required=True)
    k.add_argument("--into", default=None, help="the checkout to collect into (default: this code's own checkout)")
    a = ap.parse_args(argv)
    if a.repo:
        C.ROOT = Path(a.repo).resolve()                       # read at call time by load_main, _repo and store_dir
    try:
        if a.cmd == "create":
            r = create(Path(a.dest), ref=a.ref)
        else:
            into = Path(a.into) if a.into else C.ROOT
            r = collect(Path(a.sandbox), repo=into, log_path=into / "results/exploration/log.csv")
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

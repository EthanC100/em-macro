"""Q019: the only way exploration reads data. A frozen extract of public, point-in-time series, truncated at MAIN's
explorer.data_end (config/night.yaml on origin/main, through logs.main_cutoff / config.load_main), served by a loader
that trusts only origin/main's manifest.

Where things live:
* ``config/exploration_manifest.json`` (public, protected on main): the allowlist (``sources``: explicit repository
  files, each column with its public ``source``, its ``licence`` basis and ``point_in_time: true``; ``excluded``:
  the columns left out and why) and, once built, ``extract``: data_end, last_date, rows, bytes, sha256, the private
  store path and commit, provenance and the series list. Only this manifest and its hashes are public.
* the extract itself (``date,series,value`` rows, nothing after data_end) lives in the private store
  EthanC100/em-macro-data at ``extract.store_path``. The night shift never writes there.
* this module (builder, loader, gate), ``nightshift/explore_sandbox.py`` (the explorer's sandbox) and
  ``nightshift/logs.py`` (the variant log's cutoff check), all protected on main.

Builder (``build``): opens only the files the manifest lists and takes only the listed columns; refuses forward-looking
or revised-vintage names, columns not marked point-in-time, licensed sources (hard rule 7) and paths outside the
source root. Each source is read **as bytes, line by line**: the date must be the first column, ISO YYYY-MM-DD and
ascending; the first ten bytes of each line are compared with main's cutoff before the line is decoded or split, and
reading stops at the first later line, so no row after the cutoff is ever decoded, tokenised, parsed or converted.
Nothing is written unless every source passes. **The night shift never builds a real extract**: the first real build
is Ethan's, or a session he authorises (``--authorised-by``), and the CLI refuses while a night routine holds the lock.

Loader (``load``): in a full checkout it reads main's cutoff, fetches origin/main fresh, reads the manifest from
origin/main's objects through ``git show`` (never the checkout, which may be dev), fetches the extract from the private
store (``EM_MACRO_DATA``/``../em-macro-data``, else a temporary blobless clone that downloads that one file), checks
its sha256 against main's manifest, refuses a checkout copy of the manifest that differs from main's, and refuses
any row after main's cutoff or naming a series not in the manifest. Inside the explorer's sandbox (a directory with
``.explore/sandbox.json`` and no ``.git``) it reads only the sandbox bundle, which ``explore_sandbox create`` built
and verified the same way, and never touches git or the network.

Gate (``explorer_gate``): the reasons night-explorer may not run (empty list = may run): main's cutoff and manifest
must load as above, the four protected files must exist on origin/main, main's CODEOWNERS protected block must cover
them, and main's night-explorer routine must run the explorer in the sandbox. ``nightshift.guard`` applies it to
``check night-explorer``, ``next`` and ``state acquire``; ``explore_sandbox create`` applies it again.

  python -m nightshift.explore_data status                     # the gate, as JSON (exit 0 open, 4 closed)
  python -m nightshift.explore_data build --authorised-by NAME --store-root DIR [--manifest P] [--src-root D]
  python -m nightshift.explore_data pin --store-root DIR [--manifest P]   # record the store commit holding the extract
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path, PurePosixPath

from . import config as C
from . import logs as LG
from . import protected as P

MANIFEST_REL = "config/exploration_manifest.json"
SANDBOX_REL = "nightshift/explore_sandbox.py"
MUST_PROTECT = ("nightshift/explore_data.py", SANDBOX_REL, MANIFEST_REL, "nightshift/logs.py")
ROUTINE_REL = ".claude/routines/night-explorer.md"
SANDBOX_MARK = "python -m nightshift.explore_sandbox create"    # main's routine must run the explorer in a sandbox
REMOTE, BRANCH = C.MAIN_REMOTE, C.MAIN_BRANCH
HEADER = ["date", "series", "value"]
DATA_REPO = "EthanC100/em-macro-data"
TOKEN_ENV = "DATA_REPO_READ_TOKEN"      # read-only token (environments without the Claude Code git proxy); never printed
STORE_PREFIX = "exploration/"
BUNDLE = ".explore"                     # the sandbox bundle directory (explore_sandbox create)

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ISO_B = re.compile(rb"^\d{4}-\d{2}-\d{2}$")
# Forward-looking or revised-vintage names (column or series), e.g. country_month_panel's debt_change_next5y_pp.
FORWARD = re.compile(r"next|fwd|forward|lead|ahead|future|revis|vintage|latest|final|expost|ex_post")
# Licensed material never enters the extract (hard rule 7): checked on each source's path, source and licence text.
LICENSED = re.compile(r"norgate|databento|settlement|em-macro-data|em_macro_data", re.I)
NA = {"", "na", "n/a", "#n/a", "nan", ".", "null"}


class Refused(RuntimeError):
    """The builder or the loader refused. Nothing was written (builder) or served (loader)."""


# --------------------------------------------------------------------------------------------------- shared
def _repo(repo) -> Path:
    return Path(repo) if repo is not None else C.ROOT     # read at call time (tests point it at a scratch repo)


def _cutoff() -> date:
    """main's explorer.data_end, fetched fresh; never the checkout's config."""
    try:
        return LG.main_cutoff()
    except LG.CutoffUnreadable as e:
        raise Refused(f"main's cutoff (explorer.data_end) is unreadable: {e}") from e


def _git(repo: Path, *a: str, env: dict | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *a], cwd=repo, capture_output=True, timeout=timeout,
                          env={**(env or os.environ), "GIT_TERMINAL_PROMPT": "0"})


def _fetch_main(repo: Path) -> None:
    try:
        f = _git(repo, "fetch", "-q", REMOTE, f"+refs/heads/{BRANCH}:refs/remotes/{REMOTE}/{BRANCH}")
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Refused(f"git fetch {REMOTE} {BRANCH} failed: {e}") from e
    if f.returncode != 0:
        raise Refused(f"git fetch {REMOTE} {BRANCH} failed: {f.stderr.decode(errors='replace').strip()[-200:]}")


def _show_main(repo: Path, rel: str) -> bytes | None:
    s = _git(repo, "show", f"{REMOTE}/{BRANCH}:{rel}")
    return s.stdout if s.returncode == 0 else None


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def in_sandbox(root: Path) -> bool:
    """A sandbox made by explore_sandbox create: the bundle is there and there is no git repository."""
    return (root / BUNDLE / "sandbox.json").is_file() and not (root / ".git").exists()


# --------------------------------------------------------------------------------------------------- manifest
def check_manifest(man, cutoff: date, where: str = f"{REMOTE}/{BRANCH}") -> dict:
    """A built manifest's ``extract`` section, validated against the cutoff; raises Refused."""
    try:
        ext = man["extract"]
        sha, data_end = str(ext["sha256"]), date.fromisoformat(str(ext["data_end"]))
        ids = [str(s["id"]) for s in ext["series"]]
        store_path = str(ext["store_path"])
    except (ValueError, KeyError, TypeError) as e:
        raise Refused(f"{MANIFEST_REL} on {where} is not a built manifest: {type(e).__name__}: {e}") from e
    if not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise Refused(f"{MANIFEST_REL} on {where}: extract.sha256 is not a sha256")
    if not ids or len(set(ids)) != len(ids):
        raise Refused(f"{MANIFEST_REL} on {where} lists no series, or a series twice")
    sp = PurePosixPath(store_path)
    if sp.is_absolute() or ".." in sp.parts or not store_path.startswith(STORE_PREFIX):
        raise Refused(f"{MANIFEST_REL} on {where}: store_path {store_path!r} must be under {STORE_PREFIX}")
    if data_end > cutoff:
        raise Refused(f"the extract on {where} ends {data_end}, after main's cutoff {cutoff}")
    commit = ext.get("store_commit")
    if commit is not None and not re.fullmatch(r"[0-9a-f]{40}", str(commit)):
        raise Refused(f"{MANIFEST_REL} on {where}: store_commit is not a commit id")
    return ext


def _main_manifest(repo: Path, cutoff: date) -> tuple[dict, bytes]:
    """(manifest, its bytes) from origin/main after a fresh fetch, checked against main's cutoff."""
    _fetch_main(repo)
    mb = _show_main(repo, MANIFEST_REL)
    if mb is None:
        raise Refused(f"no {MANIFEST_REL} on {REMOTE}/{BRANCH}: the extract exists only once Ethan builds it on main")
    try:
        man = json.loads(mb.decode("utf-8"))
    except ValueError as e:
        raise Refused(f"{MANIFEST_REL} on {REMOTE}/{BRANCH} does not parse: {e}") from e
    check_manifest(man, cutoff)
    return man, mb


def _check_checkout(repo: Path, mb: bytes) -> None:
    """The checkout (dev) may lack the manifest (sparse checkout); if it has it, it must be main's, byte for byte."""
    p = repo / MANIFEST_REL
    if p.exists() and _sha(p.read_bytes()) != _sha(mb):
        raise Refused(f"the checkout's {MANIFEST_REL} differs from {REMOTE}/{BRANCH}'s: only main's copy is trusted "
                      "(edits on dev never reach exploration)")


# --------------------------------------------------------------------------------------------------- private store
def store_dir() -> Path | None:
    p = Path(os.environ.get("EM_MACRO_DATA") or (C.ROOT.parent / "em-macro-data"))
    return p if p.is_dir() else None


def _redact(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "***")
    return text


def _clone_routes() -> tuple[list[tuple[str, dict]], list[str]]:
    """Ways to reach the private store: the environment's own credentials (the Claude Code git proxy), then the
    read-only token as an HTTP header in GIT_CONFIG_* variables (never a URL, a config file or any output)."""
    base = {k: v for k, v in os.environ.items() if k != TOKEN_ENV}
    routes, secrets = [("environment credentials", dict(base))], []
    token = os.environ.get(TOKEN_ENV, "").strip()
    if token:
        b64 = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        secrets = [token, b64]
        n = int(base.get("GIT_CONFIG_COUNT") or 0)
        routes.append((TOKEN_ENV, {**base, "GIT_CONFIG_COUNT": str(n + 1),
                                   f"GIT_CONFIG_KEY_{n}": "http.https://github.com/.extraheader",
                                   f"GIT_CONFIG_VALUE_{n}": f"AUTHORIZATION: basic {b64}"}))
    return routes, secrets


def _blob_from_temp_clone(rev: str | None, path: str, notes: list[str]) -> bytes | None:
    """A temporary blobless clone without a checkout: only ``path``'s blob is downloaded, then the clone is deleted, so
    no other file of the private store (settlements, ledger) ever lands on disk."""
    url = os.environ.get("DATA_REPO_URL") or f"https://github.com/{DATA_REPO}.git"
    routes, secrets = _clone_routes()
    for name, env in routes:
        tmp = Path(tempfile.mkdtemp(prefix="explore-store-"))
        try:
            r = _git(tmp, "clone", "-q", "--filter=blob:none", "--no-checkout", "--depth", "1", "--branch", "main",
                     url, "store", env=env, timeout=300)
            if r.returncode != 0:
                notes.append(f"clone ({name}): {_redact(r.stderr.decode(errors='replace'), secrets).strip()[-160:]}")
                continue
            st = tmp / "store"
            if rev:
                f = _git(st, "fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", rev, env=env, timeout=300)
                if f.returncode != 0:
                    notes.append(f"fetch {rev[:12]} ({name}): "
                                 f"{_redact(f.stderr.decode(errors='replace'), secrets).strip()[-160:]}")
                    continue
            b = _git(st, "cat-file", "blob", f"{rev or 'HEAD'}:{path}", env=env, timeout=300)
            if b.returncode == 0:
                return b.stdout
            notes.append(f"{path} not in the clone ({name})")
        except (OSError, subprocess.TimeoutExpired) as e:
            notes.append(f"clone ({name}): {type(e).__name__}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    return None


def store_extract(ext: dict) -> bytes:
    """The extract's bytes from the private store, accepted only if their sha256 is the manifest's. Tries the store
    clone's objects (the pinned commit, then HEAD), its working file, then a temporary one-file clone."""
    path, rev, want = str(ext["store_path"]), ext.get("store_commit"), str(ext["sha256"])
    notes: list[str] = []
    cands: list[tuple[str, bytes | None]] = []
    st = store_dir()
    if st is not None:
        for r in [x for x in (rev, "HEAD") if x]:
            try:
                g = _git(st, "cat-file", "blob", f"{r}:{path}", timeout=300)
                cands.append((f"store {r[:12]}", g.stdout if g.returncode == 0 else None))
            except (OSError, subprocess.TimeoutExpired):
                cands.append((f"store {r[:12]}", None))
        f = st / path
        cands.append(("store file", f.read_bytes() if f.is_file() else None))
    for where, b in cands:
        if b is None:
            notes.append(f"{where}: absent")
        elif _sha(b) == want:
            return b
        else:
            notes.append(f"{where}: sha256 differs from main's manifest")
    b = _blob_from_temp_clone(rev, path, notes)
    if b is not None:
        if _sha(b) == want:
            return b
        notes.append("temporary clone: sha256 differs from main's manifest")
    raise Refused(f"the extract {path} with main's sha256 was not found in the private store ({DATA_REPO}): "
                  + "; ".join(notes))


# --------------------------------------------------------------------------------------------------- loader
def parse_extract(eb: bytes, ids: list[str], cutoff: date) -> list[tuple[str, str, float]]:
    """Every row's date is checked against the cutoff (as text) before its value is converted."""
    cut = cutoff.isoformat()
    rd = csv.reader(io.StringIO(eb.decode("utf-8")))
    if next(rd, None) != HEADER:
        raise Refused(f"the extract's header is not {','.join(HEADER)}")
    known, out = set(ids), []
    for n, row in enumerate(rd, start=2):
        if len(row) != 3 or not ISO.match(row[0]):
            raise Refused(f"extract line {n} is malformed")
        if row[0] > cut:                                   # text compare: the value is never converted
            raise Refused(f"extract line {n} is dated {row[0]}, after main's cutoff {cut}")
        if row[1] not in known:
            raise Refused(f"extract line {n}: series {row[1]!r} is not in main's manifest")
        try:
            v = float(row[2])
        except ValueError as e:
            raise Refused(f"extract line {n}: value {row[2]!r} is not a number") from e
        if not math.isfinite(v):
            raise Refused(f"extract line {n}: value {row[2]!r} is not finite")
        out.append((row[0], row[1], v))
    return out


def _bundle(root: Path) -> tuple[dict, bytes, date]:
    """Inside a sandbox: the bundle explore_sandbox create verified against main (no git, no network here)."""
    b = root / BUNDLE
    try:
        meta = json.loads((b / "sandbox.json").read_text(encoding="utf-8"))
        cutoff = date.fromisoformat(str(meta["cutoff"]))
        mb, eb = (b / "manifest.json").read_bytes(), (b / "extract.csv").read_bytes()
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise Refused(f"the sandbox bundle ({BUNDLE}/) is incomplete: {type(e).__name__}: {e}") from e
    if _sha(mb) != meta.get("manifest_sha256"):
        raise Refused(f"{BUNDLE}/manifest.json is not the manifest the sandbox was made with")
    man = json.loads(mb.decode("utf-8"))
    ext = check_manifest(man, cutoff, "the sandbox bundle")
    if _sha(eb) != ext["sha256"] or _sha(eb) != meta.get("extract_sha256"):
        raise Refused(f"{BUNDLE}/extract.csv does not match its manifest's sha256")
    return man, eb, cutoff


def load(series: list[str] | None = None, repo=None):
    """A DataFrame (date index, one column per series) of main's verified extract, nothing after main's cutoff.
    Raises Refused on any doubt."""
    import pandas as pd
    repo = _repo(repo)
    if in_sandbox(repo):
        man, eb, cutoff = _bundle(repo)
    else:
        cutoff = _cutoff()
        man, mb = _main_manifest(repo, cutoff)
        _check_checkout(repo, mb)
        eb = store_extract(man["extract"])
    ids = [str(s["id"]) for s in man["extract"]["series"]]
    want = list(series) if series is not None else ids
    missing = [s for s in want if s not in ids]
    if missing:
        raise Refused(f"series {missing} not in main's manifest")
    rows = [r for r in parse_extract(eb, ids, cutoff) if r[1] in want]
    df = pd.DataFrame(rows, columns=HEADER)
    df = df.pivot(index="date", columns="series", values="value").reindex(columns=want)
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    if len(df) and df.index.max() > pd.Timestamp(cutoff):
        raise Refused("extract reaches past main's cutoff")          # unreachable after parse_extract; kept
    return df


# --------------------------------------------------------------------------------------------------- gate
def explorer_gate(repo=None) -> list[str]:
    """Why night-explorer may not run; empty when main has a built manifest within its cutoff, protects the four
    files in its CODEOWNERS block, and its night-explorer routine runs the explorer in the sandbox."""
    repo = _repo(repo)
    reasons: list[str] = []
    try:
        _main_manifest(repo, _cutoff())
    except Refused as e:
        reasons.append(str(e))
    for rel in MUST_PROTECT:
        if _git(repo, "cat-file", "-e", f"{REMOTE}/{BRANCH}:{rel}").returncode != 0:
            reasons.append(f"{rel} is not on {REMOTE}/{BRANCH}")
    co = _show_main(repo, ".github/CODEOWNERS")
    try:
        pats = P.block_patterns(co.decode("utf-8")) if co is not None else []
    except ValueError:
        pats = []
    if not pats:
        reasons.append(f"no CODEOWNERS protected block on {REMOTE}/{BRANCH}")
    else:
        reasons += [f"{REMOTE}/{BRANCH}'s CODEOWNERS protected block does not cover {rel}"
                    for rel in MUST_PROTECT if not any(P.matches(q, rel) for q in pats)]
    ro = _show_main(repo, ROUTINE_REL)
    if ro is None or SANDBOX_MARK not in ro.decode("utf-8", errors="replace"):
        reasons.append(f"{REMOTE}/{BRANCH}'s {ROUTINE_REL} does not run the explorer in the sandbox "
                       f"({SANDBOX_MARK!r}): routine-level isolation is Ethan's change")
    return reasons


# --------------------------------------------------------------------------------------------------- builder
def _to_date(s: str) -> date:
    return date.fromisoformat(s)


def _to_float(s: str) -> float:
    v = float(s)
    if not math.isfinite(v):
        raise ValueError(f"not finite: {s!r}")
    return v


def _split(text: str) -> list[str]:
    """Tokenise one line already known to be on or before the cutoff."""
    return next(csv.reader([text]))


def _open_source(path: Path):
    return open(path, "rb")


def _req(d: dict, k: str, sid: str) -> str:
    v = str(d.get(k) or "").strip()
    if not v:
        raise Refused(f"source {sid}: no {k} (every column states its public source and licence basis)")
    return v


def check_sources(man: dict, src_root: Path) -> list[dict]:
    srcs = man.get("sources")
    if not isinstance(srcs, list) or not srcs:
        raise Refused("the manifest has no sources allowlist")
    root, ids, series = src_root.resolve(), set(), set()
    for s in srcs:
        sid = str(s.get("id") or "")
        if not sid or sid in ids:
            raise Refused(f"source id {sid!r} is empty or repeated")
        ids.add(sid)
        rel = str(s.get("path") or "")
        p = PurePosixPath(rel)
        if not rel or p.is_absolute() or ".." in p.parts or rel.startswith("~"):
            raise Refused(f"source {sid}: path {rel!r} must be a relative path inside the source root")
        full = (src_root / rel).resolve()
        if not full.is_relative_to(root) or not full.is_file():
            raise Refused(f"source {sid}: {rel} is not a file inside the source root")
        cols = s.get("columns")
        if not isinstance(cols, list) or not cols or not str(s.get("date_column") or ""):
            raise Refused(f"source {sid}: needs date_column and a columns list")
        excluded = {str(x.get("column")) for x in s.get("excluded") or []}
        for c in cols:
            col, ser = str(c.get("column") or ""), str(c.get("series") or "")
            if not col or not ser:
                raise Refused(f"source {sid}: a column entry needs column and series")
            text = " ".join([rel, str(s.get("source") or ""), _req(c, "source", sid), _req(c, "licence", sid)])
            if LICENSED.search(text):
                raise Refused(f"source {sid}: {col}: licensed data (Norgate, Databento, settlements, em-macro-data) "
                              "is never allowed")
            if FORWARD.search(col.lower()) or FORWARD.search(ser.lower()):
                raise Refused(f"source {sid}: {col} -> {ser} looks forward-looking or revised-vintage")
            if c.get("point_in_time") is not True:
                raise Refused(f"source {sid}: {col} is not marked point_in_time: true")
            if col in excluded:
                raise Refused(f"source {sid}: {col} is both listed and excluded")
            if ser in series:
                raise Refused(f"series {ser} is listed twice")
            series.add(ser)
    return srcs


def read_source(s: dict, src_root: Path, cut: str) -> dict[str, list[tuple[str, float]]]:
    """Rows up to the cutoff only, read as bytes. The first ten bytes of each line (the date, which must be the
    first column) are compared with the cutoff before the line is decoded or split; reading stops at the first
    later line. So no row after the cutoff is ever decoded, tokenised, parsed or converted."""
    sid, dcol = s["id"], s["date_column"]
    cutb = cut.encode("ascii")
    out: dict[str, list[tuple[str, float]]] = {c["series"]: [] for c in s["columns"]}
    with _open_source(src_root / s["path"]) as f:
        first = f.readline()
        try:
            head = _split(first.decode("utf-8-sig").rstrip("\r\n"))
        except (UnicodeDecodeError, StopIteration) as e:
            raise Refused(f"source {sid}: unreadable header in {s['path']}") from e
        if not head or head[0] != dcol:
            raise Refused(f"source {sid}: the date column {dcol!r} must be the first column of {s['path']} (so that "
                          "later rows are never tokenised)")
        need = [c["column"] for c in s["columns"]]
        absent = [k for k in need if k not in head]
        if absent:
            raise Refused(f"source {sid}: columns {absent} not in {s['path']}")
        idx = [(head.index(c["column"]), c["series"]) for c in s["columns"]]
        prev, n = b"", 1
        for line in f:
            n += 1
            line = line.rstrip(b"\r\n")
            if not line:
                continue
            d = line[:10]
            if not ISO_B.match(d) or line[10:11] not in (b",", b""):
                raise Refused(f"source {sid}: line {n} does not start with a YYYY-MM-DD date")
            if d > cutb:
                break                                     # ascending: everything from here on is after the cutoff
            if d <= prev:
                raise Refused(f"source {sid}: dates are not strictly ascending at line {n}")
            prev = d
            try:
                row = _split(line.decode("utf-8"))
            except UnicodeDecodeError as e:
                raise Refused(f"source {sid}: line {n} is not UTF-8") from e
            day = _to_date(d.decode("ascii")).isoformat()
            for i, ser in idx:
                cell = row[i].strip() if i < len(row) else ""
                if cell.lower() in NA:
                    continue
                try:
                    out[ser].append((day, _to_float(cell)))
                except ValueError as e:
                    raise Refused(f"source {sid}: {ser} value {cell!r} on line {n}: {e}") from e
    return out


def _provenance(src_root: Path, rel: str) -> dict:
    """The source file's commit and blob when the source root is a git checkout; refuses a modified file, so the
    build can be reproduced from the commit."""
    head = _git(src_root, "rev-parse", "HEAD")
    if head.returncode != 0:
        return {"commit": None, "blob": None}
    dirty = _git(src_root, "status", "--porcelain", "--", rel)
    if dirty.returncode != 0 or dirty.stdout.strip():
        raise Refused(f"{rel} differs from the checkout's HEAD: build from a clean, committed source")
    blob = _git(src_root, "rev-parse", f"HEAD:{rel}")
    return {"commit": head.stdout.decode().strip(), "blob": blob.stdout.decode().strip() or None}


def build(manifest_path: Path, src_root: Path | None = None, store_root: Path | None = None,
          authorised_by: str | None = None) -> dict:
    """Write the extract under store_root at the manifest's ``store.path`` from the allowlisted sources, cut at main's
    cutoff, and return the manifest with its ``extract`` section (the caller writes it). Refused (nothing written)
    on any doubt."""
    manifest_path = Path(manifest_path)
    src_root = Path(src_root) if src_root is not None else C.ROOT
    if store_root is None:
        raise Refused("no store root: the extract is written only into a clone of the private store")
    store_root = Path(store_root)
    cutoff = _cutoff()
    cut = cutoff.isoformat()
    try:
        man = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"manifest unreadable: {e}") from e
    store_path = str((man.get("store") or {}).get("path") or "")
    sp = PurePosixPath(store_path)
    if not store_path.startswith(STORE_PREFIX) or ".." in sp.parts or sp.is_absolute() or not store_path.endswith(".csv"):
        raise Refused(f"store.path {store_path!r} must be a .csv under {STORE_PREFIX}")
    srcs = check_sources(man, src_root)
    rows, info, prov = [], [], []
    for s in srcs:
        got = read_source(s, src_root, cut)
        prov.append({"id": s["id"], "path": s["path"], **_provenance(src_root, s["path"])})
        for c in s["columns"]:
            pts = got[c["series"]]
            rows += [(d, c["series"], v) for d, v in pts]
            info.append({"id": c["series"], "source_id": s["id"], "column": c["column"], "source": c["source"],
                         "licence": c["licence"], "n": len(pts),
                         "first": pts[0][0] if pts else None, "last": pts[-1][0] if pts else None})
    if not rows:
        raise Refused("no rows on or before the cutoff")
    rows.sort(key=lambda r: (r[0], r[1]))
    body = io.StringIO()
    w = csv.writer(body, lineterminator="\n")
    w.writerow(HEADER)
    w.writerows((d, s, repr(v)) for d, s, v in rows)
    eb = body.getvalue().encode("utf-8")
    parse_extract(eb, [i["id"] for i in info], cutoff)            # the loader's own check, before anything is written
    man["extract"] = {"store_repo": DATA_REPO, "store_path": store_path, "store_commit": None,
                      "data_end": cut, "last_date": rows[-1][0], "rows": len(rows), "bytes": len(eb),
                      "sha256": _sha(eb), "built_on": date.today().isoformat(), "authorised_by": authorised_by,
                      "sources": prov, "series": info}
    out = store_root / store_path
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(eb)
    return man


def pin(manifest_path: Path, store_root: Path) -> dict:
    """Record in the manifest the store commit that holds the extract with the manifest's sha256."""
    man = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    ext = man["extract"]
    head = _git(store_root, "rev-parse", "HEAD")
    if head.returncode != 0:
        raise Refused(f"{store_root} is not a git checkout of the private store")
    sha = head.stdout.decode().strip()
    b = _git(store_root, "cat-file", "blob", f"{sha}:{ext['store_path']}")
    if b.returncode != 0 or _sha(b.stdout) != ext["sha256"]:
        raise Refused(f"the store's HEAD {sha[:12]} does not hold {ext['store_path']} with the manifest's sha256: "
                      "commit the extract first")
    ext["store_commit"] = sha
    return man


def write_manifest(man: dict, path: Path) -> None:
    Path(path).write_text(json.dumps(man, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    b = sub.add_parser("build")
    b.add_argument("--authorised-by", required=True, help="Ethan, or the session he authorised (recorded)")
    b.add_argument("--store-root", required=True, help="a clone of the private store (em-macro-data)")
    b.add_argument("--manifest", default=str(C.ROOT / MANIFEST_REL))
    b.add_argument("--src-root", default=str(C.ROOT))
    p = sub.add_parser("pin")
    p.add_argument("--store-root", required=True)
    p.add_argument("--manifest", default=str(C.ROOT / MANIFEST_REL))
    a = ap.parse_args(argv)
    if a.cmd == "status":
        r = explorer_gate()
        print(json.dumps({"explorer_may_run": not r, "reasons": r}, indent=1))
        return 0 if not r else 4
    from . import state as S
    lk = S.load().get("lock")
    if lk:
        print(f"refused: a night routine holds the lock ({lk.get('routine')} since {lk.get('acquired_at')}): the "
              "night shift never builds a real extract")
        return 3
    try:
        if a.cmd == "pin":
            m = pin(Path(a.manifest), Path(a.store_root))
        else:
            m = build(Path(a.manifest), Path(a.src_root), Path(a.store_root), authorised_by=a.authorised_by)
    except Refused as e:
        print(f"refused: {e}")
        return 1
    write_manifest(m, Path(a.manifest))
    e = m["extract"]
    print(json.dumps({k: e[k] for k in ("store_path", "store_commit", "data_end", "last_date", "rows", "sha256")}
                     | {"series": [s["id"] for s in e["series"]]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

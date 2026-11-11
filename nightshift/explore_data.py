"""Q019: the only way exploration reads data. A frozen extract of public series, truncated at MAIN's
explorer.data_end (config/night.yaml on origin/main, through logs.main_cutoff / config.load_main), served by a
loader that trusts only origin/main.

Files (all to be protected on main by Ethan; the guard keeps night-explorer off until they are):
* ``data/exploration/manifest.json``: the allowlist (``sources``: explicit repository files, each with its public
  ``source`` and ``licence`` basis, its date column and the columns to take, each marked ``point_in_time: true``),
  and, once built, ``extract``: data_end, last_date, rows, sha256 and the series list with their sources.
* ``data/exploration/extract.csv``: ``date,series,value`` rows, nothing after data_end.
* this module (builder, loader, gate) and ``nightshift/logs.py`` (the variant log's cutoff check).

Builder (``build``): opens only the files the manifest lists, takes only the listed columns, refuses forward-looking
or revised-vintage columns and anything not marked point-in-time, refuses licensed sources (hard rule 7) and paths
outside the source root, and stops reading each file at its first row dated after main's cutoff: dates must be
ISO YYYY-MM-DD and ascending, compared as text, so no later row is tokenised, parsed or converted. Nothing is
written unless every source passes. **The night shift never builds a real extract**: the first real build is run
by Ethan or a session he authorises (``--authorised-by``), and the CLI refuses while a night routine holds the lock.

Loader (``load``): reads main's cutoff, fetches origin/main fresh, reads the manifest AND the extract from
origin/main's objects through ``git show`` (never the checkout, which may be dev or a sparse checkout without
data/), checks the sha256, refuses if the checkout's own copies differ from main's, if data_end or any row is after
main's cutoff, or if a row names a series not in the manifest.

Gate (``explorer_gate``): the reasons night-explorer may not run (empty list = may run): main's manifest and
extract must load as above, the four files must exist on origin/main and its CODEOWNERS protected block must
cover them. ``nightshift.guard`` applies it to ``check night-explorer``, ``next`` and ``state acquire``.

  python -m nightshift.explore_data status                     # the gate, as JSON (exit 0 open, 4 closed)
  python -m nightshift.explore_data build --authorised-by NAME [--manifest P] [--src-root D] [--out D]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from . import config as C
from . import logs as LG
from . import protected as P

MANIFEST_REL = "data/exploration/manifest.json"
EXTRACT_REL = "data/exploration/extract.csv"
MUST_PROTECT = ("nightshift/explore_data.py", MANIFEST_REL, EXTRACT_REL, "nightshift/logs.py")
REMOTE, BRANCH = C.MAIN_REMOTE, C.MAIN_BRANCH
HEADER = ["date", "series", "value"]

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")
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


def _git(repo: Path, *a: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *a], cwd=repo, capture_output=True, timeout=120)


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


# --------------------------------------------------------------------------------------------------- loader
def _main_extract(repo: Path, cutoff: date) -> tuple[dict, bytes, bytes]:
    """(manifest, manifest bytes, extract bytes) from origin/main after a fresh fetch, checked against each other
    and against main's cutoff."""
    _fetch_main(repo)
    mb = _show_main(repo, MANIFEST_REL)
    if mb is None:
        raise Refused(f"no {MANIFEST_REL} on {REMOTE}/{BRANCH}: the extract exists only once Ethan builds it on main")
    try:
        man = json.loads(mb.decode("utf-8"))
        ext = man["extract"]
        sha, data_end = str(ext["sha256"]), date.fromisoformat(str(ext["data_end"]))
        ids = [str(s["id"]) for s in ext["series"]]
    except (ValueError, KeyError, TypeError) as e:
        raise Refused(f"{MANIFEST_REL} on {REMOTE}/{BRANCH} is not a built manifest: {type(e).__name__}: {e}") from e
    if not ids:
        raise Refused(f"{MANIFEST_REL} on {REMOTE}/{BRANCH} lists no series")
    if data_end > cutoff:
        raise Refused(f"main's extract ends {data_end}, after main's cutoff {cutoff}")
    eb = _show_main(repo, EXTRACT_REL)
    if eb is None:
        raise Refused(f"no {EXTRACT_REL} on {REMOTE}/{BRANCH}")
    if _sha(eb) != sha:
        raise Refused(f"{EXTRACT_REL} on {REMOTE}/{BRANCH} does not match its manifest's sha256")
    return man, mb, eb


def _check_checkout(repo: Path, mb: bytes, eb: bytes) -> None:
    """The checkout (dev) may lack the files (sparse checkout); if it has them they must be main's, byte for byte."""
    for rel, want in ((EXTRACT_REL, eb), (MANIFEST_REL, mb)):
        p = repo / rel
        if p.exists() and _sha(p.read_bytes()) != _sha(want):
            raise Refused(f"the checkout's {rel} differs from {REMOTE}/{BRANCH}'s: only main's copy is trusted "
                          "(edits on dev never reach exploration)")


def _parse_extract(eb: bytes, ids: list[str], cutoff: date) -> list[tuple[str, str, float]]:
    cut = cutoff.isoformat()
    rd = csv.reader(io.StringIO(eb.decode("utf-8")))
    if next(rd, None) != HEADER:
        raise Refused(f"{EXTRACT_REL} header is not {','.join(HEADER)}")
    known, out = set(ids), []
    for n, row in enumerate(rd, start=2):
        if len(row) != 3 or not ISO.match(row[0]):
            raise Refused(f"{EXTRACT_REL} line {n} is malformed")
        if row[0] > cut:                                   # text compare: the value is never converted
            raise Refused(f"{EXTRACT_REL} line {n} is dated {row[0]}, after main's cutoff {cut}")
        if row[1] not in known:
            raise Refused(f"{EXTRACT_REL} line {n}: series {row[1]!r} is not in main's manifest")
        out.append((row[0], row[1], float(row[2])))
    return out


def load(series: list[str] | None = None, repo=None):
    """A DataFrame (date index, one column per series) of main's verified extract, nothing after main's cutoff.
    Raises Refused on any doubt."""
    import pandas as pd
    repo = _repo(repo)
    cutoff = _cutoff()
    man, mb, eb = _main_extract(repo, cutoff)
    _check_checkout(repo, mb, eb)
    ids = [str(s["id"]) for s in man["extract"]["series"]]
    want = list(series) if series is not None else ids
    missing = [s for s in want if s not in ids]
    if missing:
        raise Refused(f"series {missing} not in main's manifest")
    rows = [r for r in _parse_extract(eb, ids, cutoff) if r[1] in want]
    df = pd.DataFrame(rows, columns=HEADER)
    df = df.pivot(index="date", columns="series", values="value").reindex(columns=want)
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"
    if len(df) and df.index.max() > pd.Timestamp(cutoff):
        raise Refused("extract reaches past main's cutoff")          # unreachable after _parse_extract; kept
    return df


# --------------------------------------------------------------------------------------------------- gate
def explorer_gate(repo=None) -> list[str]:
    """Why night-explorer may not run; empty when main has the verified extract and protects all four files."""
    repo = _repo(repo)
    reasons: list[str] = []
    try:
        cutoff = _cutoff()
        man, mb, eb = _main_extract(repo, cutoff)
        _parse_extract(eb, [str(s["id"]) for s in man["extract"]["series"]], cutoff)
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
    return reasons


# --------------------------------------------------------------------------------------------------- builder
def _open_source(path: Path):
    return open(path, newline="", encoding="utf-8-sig")


def _to_date(s: str) -> date:
    return date.fromisoformat(s)


def _to_float(s: str) -> float:
    v = float(s)
    if not math.isfinite(v):
        raise ValueError(f"not finite: {s!r}")
    return v


def _check_sources(man: dict, src_root: Path) -> list[dict]:
    srcs = man.get("sources")
    if not isinstance(srcs, list) or not srcs:
        raise Refused("the manifest has no sources allowlist")
    root, ids, series = src_root.resolve(), set(), set()
    for s in srcs:
        sid = str(s.get("id") or "")
        if not sid or sid in ids:
            raise Refused(f"source id {sid!r} is empty or repeated")
        ids.add(sid)
        for k in ("source", "licence"):
            if not str(s.get(k) or "").strip():
                raise Refused(f"source {sid}: no {k} (every source states its public source and licence basis)")
        rel = str(s.get("path") or "")
        if LICENSED.search(" ".join(str(s.get(k) or "") for k in ("path", "source", "licence"))):
            raise Refused(f"source {sid}: licensed data (Norgate, Databento, settlements, em-macro-data) is never "
                          "allowed")
        p = Path(rel)
        if not rel or p.is_absolute() or ".." in p.parts:
            raise Refused(f"source {sid}: path {rel!r} must be a relative path inside the source root")
        full = (src_root / p).resolve()
        if not full.is_relative_to(root) or not full.is_file():
            raise Refused(f"source {sid}: {rel} is not a file inside the source root")
        cols = s.get("columns")
        if not isinstance(cols, list) or not cols or not str(s.get("date_column") or ""):
            raise Refused(f"source {sid}: needs date_column and a columns list")
        for c in cols:
            col, ser = str(c.get("column") or ""), str(c.get("series") or "")
            if not col or not ser:
                raise Refused(f"source {sid}: a column entry needs column and series")
            if FORWARD.search(col.lower()) or FORWARD.search(ser.lower()):
                raise Refused(f"source {sid}: {col} -> {ser} looks forward-looking or revised-vintage")
            if c.get("point_in_time") is not True:
                raise Refused(f"source {sid}: {col} is not marked point_in_time: true")
            if ser in series:
                raise Refused(f"series {ser} is listed twice")
            series.add(ser)
    return srcs


def _read_source(s: dict, src_root: Path, cut: str) -> dict[str, list[tuple[str, float]]]:
    """Rows up to the cutoff only. Reading stops at the first row dated after it: later rows are never tokenised,
    and the dates and values of rows after the cutoff are never parsed or converted."""
    sid, dcol = s["id"], s["date_column"]
    out: dict[str, list[tuple[str, float]]] = {c["series"]: [] for c in s["columns"]}
    with _open_source(src_root / s["path"]) as f:
        rd = csv.reader(f)
        head = next(rd, None) or []
        need = [dcol] + [c["column"] for c in s["columns"]]
        absent = [k for k in need if k not in head]
        if absent:
            raise Refused(f"source {sid}: columns {absent} not in {s['path']}")
        di = head.index(dcol)
        idx = [(head.index(c["column"]), c["series"]) for c in s["columns"]]
        prev = ""
        for row in rd:
            if not row:
                continue
            raw = row[di].strip() if di < len(row) else ""
            if not ISO.match(raw):
                raise Refused(f"source {sid}: date {raw!r} on line {rd.line_num} is not YYYY-MM-DD")
            if raw > cut:
                break                                     # sorted: everything from here on is after the cutoff
            if raw < prev:
                raise Refused(f"source {sid}: dates are not ascending at line {rd.line_num}")
            prev = raw
            d = _to_date(raw).isoformat()
            for i, ser in idx:
                cell = row[i].strip() if i < len(row) else ""
                if cell.lower() in NA:
                    continue
                try:
                    out[ser].append((d, _to_float(cell)))
                except ValueError as e:
                    raise Refused(f"source {sid}: {ser} value {cell!r} on line {rd.line_num}: {e}") from e
    return out


def build(manifest_path: Path, src_root: Path | None = None, out_dir: Path | None = None,
          authorised_by: str | None = None) -> dict:
    """Build extract.csv and the manifest's ``extract`` section in out_dir from the allowlisted sources, cut at
    main's cutoff. Returns the written manifest. Refused (nothing written) on any doubt."""
    manifest_path = Path(manifest_path)
    src_root = Path(src_root) if src_root is not None else C.ROOT
    out_dir = Path(out_dir) if out_dir is not None else C.ROOT / "data/exploration"
    cutoff = _cutoff()
    cut = cutoff.isoformat()
    try:
        man = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"manifest unreadable: {e}") from e
    srcs = _check_sources(man, src_root)
    rows, info = [], []
    for s in srcs:
        got = _read_source(s, src_root, cut)
        for c in s["columns"]:
            pts = got[c["series"]]
            if len({d for d, _ in pts}) != len(pts):
                raise Refused(f"source {s['id']}: repeated dates in {c['column']}")
            rows += [(d, c["series"], v) for d, v in pts]
            info.append({"id": c["series"], "source_id": s["id"], "path": s["path"], "column": c["column"],
                         "source": s["source"], "licence": s["licence"], "n": len(pts),
                         "first": pts[0][0] if pts else None, "last": pts[-1][0] if pts else None})
    if not rows:
        raise Refused("no rows on or before the cutoff")
    rows.sort(key=lambda r: (r[0], r[1]))
    body = io.StringIO()
    w = csv.writer(body, lineterminator="\n")
    w.writerow(HEADER)
    w.writerows((d, s, repr(v)) for d, s, v in rows)
    eb = body.getvalue().encode("utf-8")
    man["extract"] = {"file": "extract.csv", "data_end": cut, "last_date": rows[-1][0], "rows": len(rows),
                      "sha256": _sha(eb), "built_on": date.today().isoformat(), "authorised_by": authorised_by,
                      "series": info}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "extract.csv").write_bytes(eb)
    (out_dir / "manifest.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    return man


# --------------------------------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    b = sub.add_parser("build")
    b.add_argument("--authorised-by", required=True, help="Ethan, or the session he authorised (recorded)")
    b.add_argument("--manifest", default=str(C.ROOT / MANIFEST_REL))
    b.add_argument("--src-root", default=str(C.ROOT))
    b.add_argument("--out", default=str(C.ROOT / "data/exploration"))
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
        m = build(Path(a.manifest), Path(a.src_root), Path(a.out), authorised_by=a.authorised_by)
    except Refused as e:
        print(f"refused: {e}")
        return 1
    e = m["extract"]
    print(json.dumps({k: e[k] for k in ("data_end", "last_date", "rows", "sha256")}
                     | {"series": [s["id"] for s in e["series"]]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

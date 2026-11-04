"""Keep the raw data a trial used: compressed archives attached to the GitHub release "raw-data-archive".

Rule (README, docs/raw_data_archive.md): raw data used by any trial is kept, not only hashed.

    # 1. package a trial's raw folder (deterministic .tar.gz; split if over GitHub's asset limit)
    python -m em_macro.archive_raw pack T03 data/raw/<folder> [--out dist/raw_archive]
    # 2. or register an archive that already exists (e.g. one kept in git on a trial branch)
    python -m em_macro.archive_raw add T02 path/to/archive.tar.gz --contents "..."
    # 3. upload every pending asset to the release (needs the GitHub CLI `gh`, logged in with write access)
    python -m em_macro.archive_raw upload dist/raw_archive/<asset> [...]
    # 4. check downloaded assets against the recorded hashes
    python -m em_macro.archive_raw check dist/raw_archive/<asset> [...]

``pack`` writes ``<trial>_<folder>_raw_<date>.tar.gz`` (sorted members, fixed owner and modes, gzip header
without a timestamp, so the same files give the same bytes), a per-file manifest
``<trial>_<folder>_raw_<date>_manifest.csv`` (path, bytes, SHA-256) next to it, and records each asset with
its size and SHA-256 in docs/raw_data_archive.md.  An archive over ``PART_BYTES`` is split into
``.part001``, ``.part002``, ... (GitHub's limit is 2 GiB per release asset); restore with
``cat <asset>.part* > <asset>``.  ``upload`` creates the release if it does not exist, refuses a file whose
SHA-256 differs from the record, and never replaces an asset already on the release.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
from datetime import date
from pathlib import Path

from .config import ROOT

RELEASE_TAG = "raw-data-archive"
DOC = ROOT / "docs" / "raw_data_archive.md"
GITHUB_ASSET_LIMIT = 2 * 1024 ** 3          # 2 GiB per release asset
PART_BYTES = 1900 * 1024 ** 2               # split below the limit, with headroom
TABLE_HEADER = "| trial | asset | bytes | SHA-256 | contents | recorded | status |"
TABLE_RULE = "|---|---|---|---|---|---|---|"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _tarinfo(ti: tarfile.TarInfo) -> tarfile.TarInfo:
    ti.uid = ti.gid = 0
    ti.uname = ti.gname = ""
    ti.mtime = 0
    ti.mode = 0o755 if ti.isdir() else 0o644
    return ti


def make_archive(src: Path, out: Path) -> Path:
    """Deterministic .tar.gz of folder ``src`` (members under ``src.name/``)."""
    src = Path(src)
    out.parent.mkdir(parents=True, exist_ok=True)
    paths = sorted([src, *src.rglob("*")])
    with open(out, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as gz, \
            tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for p in paths:
            tar.add(p, arcname=str(Path(src.name) / p.relative_to(src)), recursive=False, filter=_tarinfo)
    return out


def write_manifest(src: Path, out: Path) -> Path:
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file", "bytes", "sha256"])
        for p in sorted(q for q in Path(src).rglob("*") if q.is_file()):
            w.writerow([str(Path(src.name) / p.relative_to(src)), p.stat().st_size, sha256_file(p)])
    return out


def split(path: Path, part_bytes: int = PART_BYTES, remove: bool = True) -> list[Path]:
    """Split ``path`` into .partNNN files if it is larger than ``part_bytes``; return the asset files.
    ``remove`` deletes the unsplit file afterwards (only for archives this module wrote)."""
    if path.stat().st_size <= part_bytes:
        return [path]
    parts = []
    with open(path, "rb") as f:
        i = 1
        while chunk := f.read(part_bytes):
            part = path.with_name(f"{path.name}.part{i:03d}")
            part.write_bytes(chunk)
            parts.append(part)
            i += 1
    if remove:
        path.unlink()
    return parts


# ------------------------------------------------------------------ the record
def _doc_text() -> str:
    return DOC.read_text() if DOC.exists() else ""


def recorded() -> dict[str, dict]:
    """Assets in docs/raw_data_archive.md: name -> {trial, bytes, sha256, status}."""
    out = {}
    for line in _doc_text().splitlines():
        m = re.match(r"\|\s*(\S+)\s*\|\s*`([^`]+)`\s*\|\s*(\d+)\s*\|\s*`([0-9a-f]{64})`\s*\|.*\|\s*([^|]*?)\s*\|\s*$",
                     line)
        if m:
            out[m[2]] = {"trial": m[1], "bytes": int(m[3]), "sha256": m[4], "status": m[5]}
    return out


def record(trial: str, asset: Path, contents: str, status: str = "pending upload") -> dict:
    """Add a row for ``asset`` to docs/raw_data_archive.md (an existing name must have the same hash)."""
    asset = Path(asset)
    row = {"trial": trial, "bytes": asset.stat().st_size, "sha256": sha256_file(asset), "status": status}
    have = recorded().get(asset.name)
    if have:
        if have["sha256"] != row["sha256"]:
            raise SystemExit(f"{asset.name} is already recorded with SHA-256 {have['sha256']}; "
                             f"this file is {row['sha256']}. Archives are immutable: use a new name.")
        return have
    text = _doc_text()
    if TABLE_HEADER not in text:
        raise SystemExit(f"{DOC} has no asset table ({TABLE_HEADER})")
    line = (f"| {trial} | `{asset.name}` | {row['bytes']} | `{row['sha256']}` | {contents} | "
            f"{date.today().isoformat()} | {status} |")
    lines = text.splitlines()
    i = lines.index(TABLE_RULE, lines.index(TABLE_HEADER)) + 1
    while i < len(lines) and lines[i].startswith("|"):
        i += 1
    lines.insert(i, line)
    DOC.write_text("\n".join(lines) + "\n")
    return row


def set_status(name: str, status: str) -> None:
    lines = _doc_text().splitlines()
    for i, l in enumerate(lines):
        if l.startswith("|") and f"`{name}`" in l:
            cells = l.split("|")
            cells[-2] = f" {status} "
            lines[i] = "|".join(cells)
    DOC.write_text("\n".join(lines) + "\n")


# ------------------------------------------------------------------ commands
def pack(trial: str, src: Path, out_dir: Path, contents: str | None = None) -> list[Path]:
    src = Path(src)
    if not src.is_dir() or not any(src.rglob("*")):
        raise SystemExit(f"{src} is not a non-empty folder")
    stem = f"{trial}_{src.name}_raw_{date.today().isoformat()}"
    archive = make_archive(src, Path(out_dir) / f"{stem}.tar.gz")
    manifest = write_manifest(src, Path(out_dir) / f"{stem}_manifest.csv")
    n = sum(1 for p in src.rglob("*") if p.is_file())
    desc = contents or f"`{src.as_posix()}`, {n} files"
    assets = split(archive) + [manifest]
    for a in assets:
        record(trial, a, desc if a != manifest else f"per-file SHA-256 of {stem}.tar.gz")
        print(f"{a}  {a.stat().st_size} bytes  sha256 {sha256_file(a)}")
    return assets


def _gh(*args, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check, cwd=ROOT)


def upload(files: list[Path]) -> None:
    if shutil.which("gh") is None:
        raise SystemExit("the GitHub CLI `gh` is required (https://cli.github.com), logged in with write access")
    rec = recorded()
    for f in files:
        f = Path(f)
        r = rec.get(f.name)
        if r is None:
            raise SystemExit(f"{f.name} is not recorded in {DOC}; run pack or add first")
        if sha256_file(f) != r["sha256"]:
            raise SystemExit(f"{f.name}: SHA-256 differs from the record; not uploaded")
        if f.stat().st_size > GITHUB_ASSET_LIMIT:
            raise SystemExit(f"{f.name} is over GitHub's 2 GiB asset limit; split it first")
    if _gh("release", "view", RELEASE_TAG, check=False).returncode != 0:
        _gh("release", "create", RELEASE_TAG, "--title", RELEASE_TAG, "--latest=false", "--notes",
            "Raw data used by trials, kept as compressed archives. SHA-256 of every asset: "
            "docs/raw_data_archive.md. Assets are never replaced.")
    on_release = {a["name"] for a in json.loads(_gh("release", "view", RELEASE_TAG, "--json", "assets").stdout)["assets"]}
    for f in map(Path, files):
        if f.name in on_release:
            print(f"{f.name}: already on the release, left as is")
        else:
            _gh("release", "upload", RELEASE_TAG, str(f))
            print(f"{f.name}: uploaded")
        set_status(f.name, f"on release `{RELEASE_TAG}`")


def check(files: list[Path]) -> bool:
    rec, ok = recorded(), True
    for f in map(Path, files):
        r = rec.get(f.name)
        good = r is not None and sha256_file(f) == r["sha256"]
        ok &= good
        print(f"{f.name}: {'OK' if good else 'NOT RECORDED' if r is None else 'SHA-256 MISMATCH'}")
    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack", help="archive a trial's raw folder and record it")
    p.add_argument("trial"), p.add_argument("src", type=Path)
    p.add_argument("--out", type=Path, default=ROOT / "dist" / "raw_archive"), p.add_argument("--contents")
    a = sub.add_parser("add", help="record an existing archive")
    a.add_argument("trial"), a.add_argument("file", type=Path), a.add_argument("--contents", required=True)
    u = sub.add_parser("upload", help="upload recorded assets to the release")
    u.add_argument("files", nargs="+", type=Path)
    c = sub.add_parser("check", help="check files against the recorded SHA-256")
    c.add_argument("files", nargs="+", type=Path)
    args = ap.parse_args(argv)
    if args.cmd == "pack":
        pack(args.trial, args.src, args.out, args.contents)
    elif args.cmd == "add":
        parts = split(args.file, remove=False)
        for f in parts:
            print(record(args.trial, f, args.contents))
    elif args.cmd == "upload":
        upload(args.files)
    elif args.cmd == "check":
        return 0 if check(args.files) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

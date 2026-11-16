"""Bounded, read-only artifact/backup verification against a trusted manifest.

Never builds a manifest from private data for publication. Output is counts only.
Use on explicitly authorized directories; tests use synthetic files exclusively.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path, PurePosixPath

from .inputs import read_json

MAX_FILES = 10_000
MAX_TOTAL_BYTES = 1_000_000_000


def verify(root: Path, manifest: dict) -> dict:
    """Check exact file bytes, never interpreting results or echoing filenames.

    Reject symlink components and special files. The caller must supply a stable,
    trusted local tree; this is not an isolation boundary against concurrent
    hostile filesystem mutation. Extra files are not read or treated as verified.
    """
    if not isinstance(manifest, dict) or set(manifest) != {"schema_version", "files"} \
            or type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise ValueError("unsupported artifact manifest")
    entries = manifest["files"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_FILES:
        raise ValueError("invalid artifact count")
    root = root.absolute()
    if any(p.is_symlink() for p in (root, *root.parents)) or not root.is_dir():
        raise ValueError("invalid root")
    total = 0
    seen = set()
    # Validate the whole manifest before any file read.
    for e in entries:
        if set(e) != {"path", "bytes", "sha256"} or not isinstance(e["path"], str):
            raise ValueError("invalid artifact entry")
        path = PurePosixPath(e["path"])
        if path.is_absolute() or not path.parts or ".." in path.parts or "\\" in e["path"] \
                or path.as_posix() != e["path"] or e["path"] in seen:
            raise ValueError("invalid artifact path")
        if type(e["bytes"]) is not int or not 0 <= e["bytes"] <= MAX_TOTAL_BYTES \
                or not isinstance(e["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", e["sha256"]):
            raise ValueError("invalid artifact metadata")
        seen.add(e["path"])
        total += e["bytes"]
    if total > MAX_TOTAL_BYTES:
        raise ValueError("artifact byte budget exceeded")
    missing = mismatched = verified = 0
    for e in entries:
        path = root / e["path"]
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError("symlink refused")
        try:
            mode = path.stat()
        except FileNotFoundError:
            missing += 1
            continue
        if not stat.S_ISREG(mode.st_mode):
            raise ValueError("special file refused")
        if mode.st_size != e["bytes"]:
            mismatched += 1
            continue
        digest = hashlib.sha256()
        remaining = e["bytes"]
        with path.open("rb") as source:
            while remaining:
                block = source.read(min(1_048_576, remaining))
                if not block:
                    break
                digest.update(block)
                remaining -= len(block)
            extra = source.read(1)
        if remaining or extra or digest.hexdigest() != e["sha256"]:
            mismatched += 1
        else:
            verified += 1
    return {"status": "failed" if missing or mismatched else "ok",
            "verified": verified, "missing": missing, "mismatched": mismatched}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = verify(args.root, read_json(args.manifest))
    except (ValueError, KeyError, TypeError, AttributeError, OSError):
        print('{"status":"invalid_input"}')
        return 2
    print(json.dumps(result, sort_keys=True))
    return int(result["status"] != "ok")


if __name__ == "__main__":
    raise SystemExit(main())

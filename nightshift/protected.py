"""Protected paths: read from the ``protected:start`` / ``protected:end`` block of .github/CODEOWNERS.

Patterns follow CODEOWNERS: a leading ``/`` anchors at the repository root, a trailing ``/`` means everything
under that directory, ``*`` is a glob within one path segment. Used by promotion check (c) and by the
implementer's pre-push check (``python -m nightshift.protected <paths...>`` exits 1 if any path is protected).
"""
from __future__ import annotations

import fnmatch
import sys
from pathlib import Path

from . import config as C

CODEOWNERS = C.ROOT / ".github/CODEOWNERS"


def patterns(path: Path = CODEOWNERS) -> list[str]:
    out, on = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s == "# protected:start":
            on = True
            continue
        if s == "# protected:end":
            break
        if on and s and not s.startswith("#"):
            out.append(s.split()[0])
    if not out:
        raise ValueError("no protected paths found in CODEOWNERS")
    return out


def matches(pattern: str, path: str) -> bool:
    path = path.lstrip("/")
    anchored = pattern.startswith("/")
    p = pattern.lstrip("/")
    if p.endswith("/"):
        if anchored:
            return path.startswith(p)
        return any(path[i:].startswith(p) for i in [0] + [k + 1 for k, ch in enumerate(path) if ch == "/"])
    if anchored:
        return fnmatch.fnmatchcase(path, p)
    return fnmatch.fnmatchcase(path, p) or fnmatch.fnmatchcase(path.rsplit("/", 1)[-1], p)


def protected(paths: list[str], pats: list[str] | None = None) -> list[str]:
    pats = pats if pats is not None else patterns()
    return sorted({p for p in paths if any(matches(q, p) for q in pats)})


def main(argv=None) -> int:
    paths = argv if argv is not None else sys.argv[1:]
    hit = protected(paths)
    for p in hit:
        print(f"PROTECTED: {p}")
    return 1 if hit else 0


if __name__ == "__main__":
    sys.exit(main())

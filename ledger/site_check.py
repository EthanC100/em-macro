"""Build the Ledger site the way the ledger-pages workflow does: with only the standard library and the packages of
requirements-site.txt importable.

    python -m ledger.site_check                       # build this repository into a scratch directory
    python -m ledger.site_check --root PATH --out DIR --today YYYY-MM-DD

Why (2026-11-17): from 11 to 17 Nov 2026 every ledger-pages run failed and the published site stayed at 11 Nov, while
the test suite and the night shift's promote check stayed green. C09 made the build read janus/watchlist.yaml with
``import yaml``; the pages job built with a bare Python, but the tests and promote ran with every package of
requirements.txt installed, so nothing they ran could see the missing package.

How: the build runs in a child ``python -S`` (no site-packages at all) whose PYTHONPATH is a scratch directory that
links only the top-level modules of the requirements-site.txt distributions and their dependencies. That is the pages
runner's environment (setup-python, then ``pip install -r requirements-site.txt``); tests/test_site_build.py checks
that the workflow still installs exactly that file before it builds. No private store: EM_MACRO_DATA points at a
directory that does not exist, as on the pages runner. Writes only under --out and a scratch directory.

Exit 0 when the build succeeded, 1 when it failed (the last lines of its error are printed).
"""
from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = "requirements-site.txt"


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def requirement_names(path: Path) -> list[str]:
    """Distribution names listed in a requirements file (versions, markers and comments dropped)."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", line)
        if m:
            out.append(m.group(1))
    return out


def with_dependencies(names: list[str]) -> list[md.Distribution]:
    """The installed distributions of ``names`` and everything they require (extras ignored). A name that is not
    installed here is skipped: the build then cannot import it either, and fails as the pages runner would not."""
    seen: dict[str, md.Distribution] = {}
    todo = list(names)
    while todo:
        n = _norm(todo.pop())
        if n in seen:
            continue
        try:
            dist = md.distribution(n)
        except md.PackageNotFoundError:
            continue
        seen[n] = dist
        for req in dist.requires or []:
            marker = req.split(";", 1)[1] if ";" in req else ""
            if "extra" in marker:
                continue
            m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", req)
            if m:
                todo.append(m.group(1))
    return list(seen.values())


def make_shim(dists: list[md.Distribution], shim: Path) -> list[str]:
    """Link every top-level entry of each distribution (packages, modules, extension files, its .dist-info) into
    ``shim``; returns the names linked."""
    shim.mkdir(parents=True, exist_ok=True)
    linked = []
    for dist in dists:
        tops = {f.parts[0] for f in (dist.files or []) if f.parts and f.parts[0] not in ("..", "__pycache__")}
        for top in sorted(tops):
            src = Path(dist.locate_file(top))
            dst = shim / top
            if src.exists() and not dst.exists():
                dst.symlink_to(src, target_is_directory=src.is_dir())
                linked.append(top)
    return linked


def build_like_pages(root: Path = ROOT, out: Path | None = None, today: str | None = None,
                     requirements: Path | None = None, timeout: int = 900) -> dict:
    """Run ``python -m ledger.build`` in ``root`` with only the standard library and ``requirements`` (default:
    root/requirements-site.txt) importable. {"ok", "returncode", "detail" (last lines of stderr when it failed),
    "packages" (the modules made importable)}."""
    root = Path(root)
    req = Path(requirements) if requirements else root / REQUIREMENTS
    names = requirement_names(req) if req.exists() else []
    with tempfile.TemporaryDirectory(prefix="site-check-") as tmp:
        tmp = Path(tmp)
        linked = make_shim(with_dependencies(names), tmp / "site")
        out = Path(out) if out else tmp / "app"
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("PYTHON", "VIRTUAL_ENV", "CONDA")) and k not in ("EM_MACRO_DATA", "DATA_REPO_URL")}
        env.update({"PYTHONPATH": str(tmp / "site"), "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
                    "EM_MACRO_DATA": str(tmp / "no-private-store"), "DATA_REPO_URL": str(tmp / "no-private-store.git")})
        args = [sys.executable, "-S", "-m", "ledger.build", "--out", str(out)] + (["--today", today] if today else [])
        r = subprocess.run(args, cwd=root, env=env, capture_output=True, text=True, timeout=timeout)
    tail = "\n".join((r.stderr or r.stdout).strip().splitlines()[-6:]) if r.returncode else ""
    return {"ok": r.returncode == 0, "returncode": r.returncode, "detail": tail, "packages": linked,
            "requirements": names}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--out", default=None, help="where to write the site (default: a scratch directory)")
    ap.add_argument("--today", default=None)
    a = ap.parse_args(argv)
    res = build_like_pages(Path(a.root), Path(a.out) if a.out else None, a.today)
    print(json.dumps(res, indent=1))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

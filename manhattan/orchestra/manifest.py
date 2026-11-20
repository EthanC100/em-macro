"""The execution manifest: exactly what ran, so any invocation can be reproduced or refused.

A manifest has three identities, each a SHA-256:

* ``code``: the working-tree contents of every file under the code paths (``manhattan/`` and the requirement files),
  tracked or untracked-but-not-ignored, plus the commit and whether those paths differ from it. Content, not the
  commit, is hashed: an uncommitted edit changes the identity.
* ``numeric_environment``: Python, NumPy and SciPy versions, NumPy's BLAS/LAPACK build, its SIMD baseline and
  dispatch targets, the machine type and CPU model, and the thread-count variables the child sets. Results agree
  bit for bit only within one numerical environment (docs/manhattan/hte/ARCHITECTURE.md section 6.1).
* ``packages``: every installed distribution and its version.

``identity`` (code + numeric environment + packages + job spec) is fixed at a job's registration. Every later
invocation recomputes it and must match, or the job is ``blocked`` (``code_changed`` or ``environment_changed``):
resuming a scientific job under other code or another environment would mix results silently. Re-registering under
the new identity is an explicit, separately counted look.
"""
from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from pathlib import Path

from .journal import full_hash

REPO = Path(__file__).resolve().parents[2]
CODE_PATHS = ("manhattan", "requirements.txt", "requirements-manhattan.txt", "requirements-manhattan-runner.lock")
# one thread per process in every child (the workers are the parallelism); fixed, so it is part of the identity
CHILD_THREADS = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
                 "VECLIB_MAXIMUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"}


def _git(*args: str, root: Path = REPO) -> tuple[int, str]:
    try:
        p = subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""
    return p.returncode, p.stdout.decode("utf-8", "replace")


def code_files(root: Path = REPO, paths=CODE_PATHS) -> list[str]:
    rc, out = _git("ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *paths, root=root)
    if rc == 0 and out:
        files = [f for f in out.split("\0") if f]
    else:                                             # not a git checkout: walk the paths
        files = []
        for p in paths:
            q = root / p
            if q.is_file():
                files.append(p)
            elif q.is_dir():
                files += [str(x.relative_to(root)) for x in q.rglob("*") if x.is_file() and "__pycache__" not in x.parts]
    return sorted(set(f for f in files if (root / f).is_file() and not f.endswith(".pyc")))


def code_identity(root: Path = REPO, paths=CODE_PATHS) -> dict:
    h = hashlib.sha256()
    files = code_files(root, paths)
    for f in files:
        h.update(f.encode() + b"\0")
        h.update(hashlib.sha256((root / f).read_bytes()).digest())
    rc, commit = _git("rev-parse", "HEAD", root=root)
    rc2, st = _git("status", "--porcelain", "--untracked-files=all", "--", *paths, root=root)
    return {"commit": commit.strip() if rc == 0 else "unknown",
            "dirty": bool(st.strip()) if rc2 == 0 else True,
            "paths": list(paths), "files": len(files), "content_sha256": h.hexdigest()}


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def numeric_environment() -> dict:
    env: dict = {"python": platform.python_version(), "implementation": platform.python_implementation(),
                 "machine": platform.machine(), "system": platform.system(), "cpu_model": _cpu_model(),
                 "threads": dict(CHILD_THREADS)}
    try:
        import numpy as np
        env["numpy"] = np.__version__
        try:
            cfg = np.show_config(mode="dicts")
            deps = cfg.get("Build Dependencies", {})
            env["blas"] = {f"{k}.{f}": deps.get(k, {}).get(f) for k in ("blas", "lapack")
                           for f in ("name", "version", "openblas configuration") if deps.get(k, {}).get(f)}
            simd = cfg.get("SIMD Extensions", {})
            env["simd"] = {"baseline": simd.get("baseline"), "found": simd.get("found")}
        except Exception:                             # older NumPy: versions only
            env["blas"] = None
    except ImportError:
        env["numpy"] = None
    try:
        import scipy
        env["scipy"] = scipy.__version__
    except ImportError:
        env["scipy"] = None
    return env


def packages() -> list[str]:
    from importlib import metadata
    out = set()
    for d in metadata.distributions():
        name = (d.metadata["Name"] or "").lower()
        if name:
            out.add(f"{name}=={d.version}")
    return sorted(out)


def build(job_spec: dict, root: Path = REPO, *, paths=CODE_PATHS) -> dict:
    """The full manifest of one invocation (or of a registration). ``identity`` is what must not change between a
    job's invocations; the rest is recorded for the audit."""
    code = code_identity(root, paths)
    num = numeric_environment()
    pk = packages()
    ident = {"code_sha256": code["content_sha256"], "numeric_environment_sha256": full_hash(num),
             "packages_sha256": full_hash(pk), "job_spec_sha256": full_hash(job_spec)}
    return {"identity": ident, "identity_sha256": full_hash(ident), "code": code, "numeric_environment": num,
            "packages": pk, "job_spec": job_spec, "executable": sys.executable, "argv0": "manhattan.orchestra.child"}


def compare(registered: dict, now: dict, *, strict_environment: bool = True) -> str | None:
    """None when the identities match, else the reason a resume is refused. ``strict_environment=False`` is for
    kinds whose units of work are pooled by code identity alone and are reproducible across machines by
    construction (the simulation's replications: seeds depend on the replication number only)."""
    if registered.get("code_sha256") != now.get("code_sha256"):
        return "code_changed"
    if strict_environment and registered.get("numeric_environment_sha256") != now.get("numeric_environment_sha256"):
        return "environment_changed"
    if strict_environment and registered.get("packages_sha256") != now.get("packages_sha256"):
        return "packages_changed"
    if registered.get("job_spec_sha256") != now.get("job_spec_sha256"):
        return "job_spec_changed"
    return None

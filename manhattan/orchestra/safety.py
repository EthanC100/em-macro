"""Fail-closed guards. The orchestrator cannot reach anything a research session may not reach by hand.

* **Child environment** (``child_env``): an allowlist, not a denylist. Only the variables named in ``KEEP`` pass, so
  no token, key, deploy key or cloud credential reaches a job (rule 10). The private store is pointed at a path that
  does not exist (as in the tests workflow), proxies point at a closed local port so that a library honouring them
  cannot reach the network, and BLAS and OpenMP run one thread per process.
* **Run root** (``check_root``): absolute, outside the repository checkout (no job can write a tracked file, a writer's
  data or a protected path, rules 2 and 3), and on a local file system (``flock`` is unreliable on network ones).
* **Manhattan switches** (``manhattan_switches``): ``config/manhattan.yaml`` is read, never written, and must validate.
  No new invocation starts while it does not, and none starts while it says that a reserve, a forward run, real
  money or claims are enabled: orchestration is for synthetic research only, and an activation is Ethan's to run
  by hand, never a queued job's.
* **Kinds**: only the allowlisted kinds in ``kinds.KINDS`` run; each validates its parameters strictly.
"""
from __future__ import annotations

import os
from pathlib import Path

from .manifest import CHILD_THREADS, REPO

KEEP = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LANGUAGE", "TZ", "TMPDIR", "PYTHONPATH", "VIRTUAL_ENV",
        "TERM")
KEEP_PREFIX = ("LC_",)
CLOSED_PROXY = "http://127.0.0.1:9"            # discard port: nothing listens; a request fails at once
NONEXISTENT_STORE = "/nonexistent/em-macro-data"
NETWORK_FS = {"nfs", "nfs4", "cifs", "smbfs", "smb3", "fuse.sshfs", "9p", "afs", "ceph", "glusterfs", "fuse.s3fs",
              "fuse.gcsfuse", "fuse.rclone", "virtiofs"}


class Refused(PermissionError):
    """A safety guard refused an action."""


def child_env(base: dict | None = None, extra: dict | None = None) -> tuple[dict, int]:
    """The environment of an invocation process, and the number of parent variables that were dropped (names are
    never logged)."""
    base = dict(os.environ if base is None else base)
    env = {k: v for k, v in base.items() if k in KEEP or k.startswith(KEEP_PREFIX)}
    dropped = len(base) - len(env)
    env.update(CHILD_THREADS)
    env.update({"EM_MACRO_DATA": NONEXISTENT_STORE, "DATA_REPO_URL": NONEXISTENT_STORE + ".git",
                "HTTP_PROXY": CLOSED_PROXY, "HTTPS_PROXY": CLOSED_PROXY, "ALL_PROXY": CLOSED_PROXY,
                "http_proxy": CLOSED_PROXY, "https_proxy": CLOSED_PROXY, "all_proxy": CLOSED_PROXY,
                "NO_PROXY": "", "no_proxy": "", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0",
                "PYTHONUNBUFFERED": "1", "MANHATTAN_ORCHESTRA_CHILD": "1",
                "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"})
    if extra:
        env.update(extra)
    return env, dropped


def _fs_type(path: Path) -> str | None:
    try:
        mounts = Path("/proc/mounts").read_text().splitlines()
    except OSError:
        return None
    best, typ = "", None
    p = str(path)
    for line in mounts:
        parts = line.split()
        if len(parts) < 3:
            continue
        mnt = parts[1].replace("\\040", " ")
        if (p == mnt or p.startswith(mnt.rstrip("/") + "/")) and len(mnt) >= len(best):
            best, typ = mnt, parts[2]
    return typ


def check_root(root: Path, repo: Path = REPO) -> Path:
    root = Path(root)
    if not root.is_absolute():
        raise Refused("the run root must be an absolute path")
    r = root.resolve()
    rp = Path(repo).resolve()
    if r == rp or rp in r.parents or r in rp.parents:
        raise Refused(f"the run root must be outside the repository checkout ({rp}) and must not contain it")
    typ = _fs_type(r if r.exists() else r.parent)
    if typ in NETWORK_FS:
        raise Refused(f"the run root is on a network file system ({typ}); locks need a local disk")
    return r


def manhattan_switches(repo: Path = REPO) -> list[str]:
    """Reasons no new invocation may start, from the Manhattan switches (read only). Empty means go."""
    try:
        from manhattan import config as MC
    except Exception as e:                       # fail closed
        return [f"manhattan.config unavailable: {type(e).__name__}"]
    path = Path(repo) / "config" / "manhattan.yaml"
    try:
        cfg = MC.load(path)
        errors = list(MC.validate(cfg))
    except Exception as e:
        return [f"config/manhattan.yaml unreadable: {type(e).__name__}"]
    reasons = [f"config/manhattan.yaml invalid: {x}" for x in errors]
    g = lambda *ks: _get(cfg, ks)
    if g("reserve", "enabled") is not False:
        reasons.append("reserve.enabled is not false")
    if g("forward", "real_money") is not False:
        reasons.append("forward.real_money is not false")
    if g("claims", "enabled") is not False:
        reasons.append("claims.enabled is not false")
    return reasons


def _get(d, ks):
    for k in ks:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d

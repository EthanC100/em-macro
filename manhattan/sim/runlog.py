"""The run log (SIM_PREREG section 9) and the held-out fence (section 8.1).

Every simulation run appends records to ``results/manhattan_sim/runs.jsonl``: one when it starts and one when it
ends (``completed``, ``failed`` or ``interrupted``). A start with no end is an abandoned run and stays visible.
Each record carries the time, the commit (and whether the tree was dirty), the protocol hash, the
pre-registration hash, the scenario, the size, the held-out set if any, the replications, the seeds and the
status.

A held-out scenario runs only in a confirmation run: the caller must name the set ``k`` and the checked-out
commit must carry the tag ``manhattan-sim-confirm-<k>`` on a clean tree. Anything else is refused, and the refusal
is logged as a record with status ``refused``.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from manhattan import prereg

from . import seeds

RUNS = prereg.ROOT / "results/manhattan_sim/runs.jsonl"
PROTOCOL = "docs/manhattan/PROTOCOL_v3.md"
TAG = "manhattan-sim-confirm-{k}"
OUTPUTS = ":(exclude)results/manhattan_sim"     # the log and the results are outputs: they do not make a tree dirty
FIELDS = ("run_id", "event", "time_utc", "commit", "dirty", "protocol_sha256", "prereg_sha256", "scenario", "size",
          "heldout_set", "label", "replications", "seeds", "status")


class HeldOutRefused(RuntimeError):
    """A held-out scenario was asked for outside a tagged confirmation run."""


def _git(*args: str, root: Path = prereg.ROOT) -> str:
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def git_state(root: Path = prereg.ROOT) -> dict:
    """Commit, whether tracked files other than this package's own outputs differ from it, and the tags on it."""
    return {"commit": _git("rev-parse", "HEAD", root=root) or "unknown",
            "dirty": bool(_git("status", "--porcelain", "--untracked-files=no", "--", ".", OUTPUTS, root=root)),
            "tags": [t for t in _git("tag", "--points-at", "HEAD", root=root).splitlines() if t]}


def protocol_hash(root: Path = prereg.ROOT) -> str:
    return hashlib.sha256((root / PROTOCOL).read_bytes()).hexdigest()


def append(record: dict, path: Path = RUNS) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    return record


def read(path: Path = RUNS) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _record(event: str, status: str, *, run_id: str, scenario: str, size: str, heldout_set, label: str,
            replications: dict, seed_info: dict, git: dict, sha: str, root: Path, extra: dict | None = None) -> dict:
    rec = {"run_id": run_id, "event": event, "time_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "commit": git["commit"], "dirty": git["dirty"], "protocol_sha256": protocol_hash(root),
           "prereg_sha256": sha, "scenario": scenario, "size": size, "heldout_set": heldout_set, "label": label,
           "replications": replications, "seeds": seed_info, "status": status}
    rec.update(extra or {})
    return rec


def check_heldout(is_heldout: bool, confirm: int | None, git: dict) -> None:
    """Raise ``HeldOutRefused`` unless a held-out scenario is being run in a tagged confirmation run."""
    if not is_heldout:
        if confirm is not None and TAG.format(k=confirm) not in git["tags"]:
            raise HeldOutRefused(f"a confirmation run needs the tag {TAG.format(k=confirm)} on the checked-out commit")
        return
    if confirm is None:
        raise HeldOutRefused("held-out scenarios run only in a confirmation run (SIM_PREREG section 8.1): "
                             "pass the held-out set and run from the tagged commit")
    if TAG.format(k=confirm) not in git["tags"]:
        raise HeldOutRefused(f"the checked-out commit does not carry the tag {TAG.format(k=confirm)}")
    if git["dirty"]:
        raise HeldOutRefused("a confirmation run needs a clean working tree")


def start(*, scenario: str, size: str, is_heldout: bool, confirm: int | None, label: str, reps: range,
          branch: int, options: dict | None = None, path: Path = RUNS, root: Path = prereg.ROOT,
          git: dict | None = None) -> dict:
    """Log the start of a run and return its record. Refuses (and logs the refusal of) a held-out run that is
    not a tagged confirmation run."""
    git = git or git_state(root)
    sha = seeds.prereg_hash(root)
    common = dict(run_id=uuid.uuid4().hex[:12], scenario=scenario, size=size, heldout_set=confirm, label=label,
                  replications={"first": reps.start, "requested": len(reps), "completed": 0},
                  seed_info={"master": seeds.master_seed(sha), "branch": branch,
                             "scenario_key": seeds.scenario_key(scenario), "size_key": seeds.SIZE_KEY[size]},
                  git=git, sha=sha, root=root, extra={"options": options or {}})
    try:
        check_heldout(is_heldout, confirm, git)
    except HeldOutRefused as e:
        append(_record("refused", "refused", **{**common, "extra": {"options": options or {}, "reason": str(e)}}), path)
        raise
    return append(_record("start", "started", **common), path)


def finish(start_record: dict, status: str, completed: int, *, path: Path = RUNS, extra: dict | None = None) -> dict:
    """Log the end of a run: ``completed``, ``failed`` or ``interrupted``."""
    if status not in ("completed", "failed", "interrupted"):
        raise ValueError("status must be completed, failed or interrupted")
    rec = {k: start_record[k] for k in FIELDS if k in start_record}
    rec.update(event="end", status=status, time_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               replications={**start_record["replications"], "completed": completed},
               options=start_record.get("options", {}))
    rec.update(extra or {})
    return append(rec, path)

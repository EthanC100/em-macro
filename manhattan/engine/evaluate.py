"""One evaluation, on record: run a strategy on a window and write what was done.

Every evaluation is a record of a Manhattan ledger (ARCHITECTURE section 4): the executable, the window, the
role ``manhattan.roles.check_read`` gave the read, the hash of the data, the hash of the result and the code
version. A second identical evaluation is a ``rerun`` (the same look); a different result on the same key is a
``nondeterminism``. An **exploration-role** evaluation is also one row of the exploration variant log
(``nightshift.logs.log_variant``, CLAUDE.md hard rule 6), whose ``code_ref`` is the ledger record's hash; that
log refuses any window ending after the exploration cut-off (2019-12-31).

The ledger holds outcomes, so it is a private file (ARCHITECTURE section 4.1) unless every record in it is of
the exploration role, whose results anyone may read.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from manhattan import ledger as L
from manhattan import roles, spec

from . import backtest
from .pit import Window

ROOT = Path(__file__).resolve().parents[2]


def code_version(root: Path = ROOT) -> dict:
    """The git commit and the SHA-256 of the engine's source files."""
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    h = hashlib.sha256()
    for p in sorted((root / "manhattan/engine").glob("*.py")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return {"commit": commit, "engine_sha256": h.hexdigest()}


def evaluate(window: Window, strategy: backtest.Strategy, *, ledger: L.Ledger, executable: dict, variant: dict,
             hypothesis: dict, family: dict, batch: str = "exploration", channel: str = "blind",
             designated: bool = False, window_id: str | None = None, seed: int = 0, description: str = "",
             log_path: Path | None = None, version: dict | None = None) -> tuple[backtest.Result, dict]:
    """Run ``strategy`` over ``window`` and record it. Returns the result and the ledger record.

    ``executable``, ``variant``, ``hypothesis`` and ``family`` are spec mappings (``manhattan.spec``).
    ``log_path``: where the exploration variant row goes (required for an exploration-role window)."""
    if window.role == roles.EXPLORATION and log_path is None:
        raise ValueError("an exploration-role evaluation is also logged as a variant: give log_path")
    result = backtest.run(window, strategy)
    s = result.summary()
    win = {"id": window_id or f"{window.domain}:{window.start}:{window.end}", "start": window.start, "end": window.end,
           "frequency": "daily"}
    rec = ledger.record_evaluation(
        executable=spec.spec_id(executable), variant=spec.spec_id(variant), hypothesis=spec.spec_id(hypothesis),
        family=spec.spec_id(family), batch=batch, channel=channel, role=window.role, window=win,
        designated=designated, spec_hash=spec.spec_hash(executable), data_hash=window.data_hash(),
        code_version=version or code_version(), result_hash=result.result_hash(), n_obs=s["n_obs"],
        summary={k: (round(v, 10) if isinstance(v, float) and v == v else (None if isinstance(v, float) else v))
                 for k, v in s.items()}, seed=seed)
    if window.role == roles.EXPLORATION and rec["type"] == "evaluation":
        from nightshift import logs
        logs.log_variant({"hypothesis_id": spec.spec_id(hypothesis), "variant_id": spec.spec_id(executable),
                          "description": description or f"Manhattan engine evaluation of {spec.spec_id(executable)}",
                          "data_start": str(window.start), "data_end": str(window.end), "n_obs": str(s["n_obs"]),
                          "metric": "sharpe_annual_net", "value": f"{s['sharpe']:.6f}",
                          "params": f"rebalance={strategy.rebalance};lag={strategy.lag};vol_target={strategy.vol_target}",
                          "code_ref": rec["hash"], "nominated": "", "notes": f"ledger seq {rec['seq']}"}, path=log_path)
    return result, rec

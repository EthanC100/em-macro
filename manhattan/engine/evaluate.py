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
from .pit import PitError, Window

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


def _identity_now(window: Window, *, executable, variant, hypothesis, family, batch, channel, designated,
                  window_id, version) -> dict:
    win = {"id": window_id or f"{window.domain}:{window.start}:{window.end}", "start": str(window.start),
           "end": str(window.end), "frequency": "daily"}
    return {"executable": spec.spec_id(executable), "variant": spec.spec_id(variant),
            "hypothesis": spec.spec_id(hypothesis), "family": spec.spec_id(family), "batch": batch,
            "channel": channel, "role": window.role, "designated": bool(designated),
            "spec_hash": spec.spec_hash(executable), "data_hash": window.data_hash(), "window": win,
            "code_version": version}


def evaluate(window: Window, strategy: backtest.Strategy, *, ledger: L.Ledger, executable: dict, variant: dict,
             hypothesis: dict, family: dict, batch: str = "exploration", channel: str = "blind",
             designated: bool = False, window_id: str | None = None, seed: int = 0, description: str = "",
             log_path: Path | None = None, version: dict | None = None, attempt=None) -> tuple[backtest.Result, dict]:
    """Run ``strategy`` over ``window`` and record it. Returns the result and the ledger record.

    ``executable``, ``variant``, ``hypothesis`` and ``family`` are spec mappings (``manhattan.spec``).
    ``log_path``: where the exploration variant row goes (required for an exploration-role window).

    ``attempt`` (Phase 4B): the ``manhattan.access.AttemptContext`` registered for this evaluation, required for a
    reserve or forward window and for any window opened under an attempt. Before anything runs, the window must be
    the attempt's declared evaluation window, and the identity this call would record (spec IDs, batch, channel,
    role, designated, spec and data hash, window and the running code's identity) must equal the registered one;
    otherwise the attempt is closed as ``failed: validation_error`` and nothing is computed. A failure while
    computing closes it as ``failed: execution_error``; an interruption as ``aborted: interrupted``. Only a
    classified reason is written, never the exception."""
    from manhattan.engine.pit import PROTECTED_ROLES, AccessError

    if window.purpose == "diagnostic":
        raise AccessError("a diagnostic window never produces an evaluation record")
    bound = window.role in PROTECTED_ROLES or window.attempt_id is not None or attempt is not None
    if bound:
        from manhattan import access
        if not isinstance(attempt, access.AttemptContext) or attempt.kind != "engine_evaluation":
            raise AccessError("a protected evaluation needs its registered attempt (manhattan.access)")
        if not isinstance(attempt._backend, access._LedgerBackend) or attempt._backend.ledger is not ledger:
            raise AccessError("the attempt is registered in a different ledger")
        attempt.check_evaluation_window(window)
        now = _identity_now(window, executable=executable, variant=variant, hypothesis=hypothesis, family=family,
                            batch=batch, channel=channel, designated=designated,
                            window_id=window_id or attempt.evaluation_window.id,
                            version=version or code_version())
        if now != attempt.identity:
            attempt.fail("validation_error")
            raise AccessError("the evaluation differs from its registered identity (or the running code does)")
    try:
        if window.role == roles.EXPLORATION and log_path is None:
            raise ValueError("an exploration-role evaluation is also logged as a variant: give log_path")
        if window.role == roles.RESERVE:
            window.require_historical_evidence()
        if window.role == roles.FORWARD and window.reconstructed:
            raise PitError("forward evaluation requires per-observation provenance; "
                           "store-wide reconstructed status cannot attribute forward evidence")
    except (ValueError, PitError):
        if bound:
            attempt.fail("validation_error")
        raise
    try:
        result = backtest.run(window, strategy)
    except Exception:
        if bound:
            attempt.fail("execution_error")
        raise
    except KeyboardInterrupt:
        if bound:
            attempt.abort("interrupted")
        raise
    s = result.summary()
    if bound:
        win = attempt.identity["window"]
        version = attempt.identity["code_version"]
    else:
        win = {"id": window_id or f"{window.domain}:{window.start}:{window.end}", "start": window.start,
               "end": window.end, "frequency": "daily"}
        version = version or code_version()
    rec = ledger.record_evaluation(
        executable=spec.spec_id(executable), variant=spec.spec_id(variant), hypothesis=spec.spec_id(hypothesis),
        family=spec.spec_id(family), batch=batch, channel=channel, role=window.role, window=win,
        designated=designated, spec_hash=spec.spec_hash(executable), data_hash=window.data_hash(),
        code_version=version, result_hash=result.result_hash(), n_obs=s["n_obs"],
        summary={k: (round(v, 10) if isinstance(v, float) and v == v else (None if isinstance(v, float) else v))
                 for k, v in s.items()}, seed=seed, reconstructed=window.reconstructed,
        attempt_id=attempt.attempt_id if bound else None)
    if bound:
        attempt._mark_completed()
    if window.role == roles.EXPLORATION and rec["type"] == "evaluation":
        from nightshift import logs
        logs.log_variant({"hypothesis_id": spec.spec_id(hypothesis), "variant_id": spec.spec_id(executable),
                          "description": description or f"Manhattan engine evaluation of {spec.spec_id(executable)}",
                          "data_start": str(window.start), "data_end": str(window.end), "n_obs": str(s["n_obs"]),
                          "metric": "sharpe_annual_net", "value": f"{s['sharpe']:.6f}",
                          "params": f"rebalance={strategy.rebalance};lag={strategy.lag};vol_target={strategy.vol_target}",
                          "code_ref": rec["hash"], "nominated": "", "notes": f"ledger seq {rec['seq']}"}, path=log_path)
    return result, rec

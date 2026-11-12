"""Atlas switches: config/atlas.yaml (docs/atlas/ARCHITECTURE.md section 9).

    python -m atlas.config check       # exit 1 if the file is not valid

Ethan sets the file on main; runners read main's copy. Every default is the conservative one. ``validate`` checks
the shape of the file and the rules that hold whatever Ethan chooses: no real-money execution exists, a reserve
needs a fence, a level is never looser than Protocol v3's, and claims need a screening method chosen by the
simulation.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/atlas.yaml"
SCREENING_FDR_MAX, FORWARD_FDR_MAX = 0.20, 0.05          # Protocol v3 section 3
SCREENING_METHODS = (None, "batch_bh_prds", "ebh_elond")   # Protocol v3 sections 4.3 and 4.4


def load(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _day(v) -> date | None:
    try:
        return v if isinstance(v, date) else date.fromisoformat(str(v))
    except ValueError:
        return None


def validate(cfg: dict) -> list[str]:
    errs = []

    def get(section: str, key: str):
        s = cfg.get(section)
        if not isinstance(s, dict) or key not in s:
            errs.append(f"{section}.{key} is required")
            return None
        return s[key]

    if get("freeze", "authority") not in (None, "ethan_only", "delegated"):
        errs.append("freeze.authority must be ethan_only or delegated")
    enabled, windows = get("reserve", "enabled"), get("reserve", "windows")
    if enabled not in (None, True, False):
        errs.append("reserve.enabled must be true or false")
    if get("reserve", "mode") not in (None, "shared_window", "disjoint_slices"):
        errs.append("reserve.mode must be shared_window or disjoint_slices")
    if get("reserve", "evaluate_adaptive") not in (None, True, False):
        errs.append("reserve.evaluate_adaptive must be true or false")
    if get("reserve", "store") not in (None, "imac_only", "private_repo"):
        errs.append("reserve.store must be imac_only or private_repo")
    if windows is not None and not isinstance(windows, dict):
        errs.append("reserve.windows must map a domain to {start, end}")
        windows = None
    for dom, w in (windows or {}).items():
        a, b = (_day(w.get("start")), _day(w.get("end"))) if isinstance(w, dict) else (None, None)
        if a is None or b is None or a >= b:
            errs.append(f"reserve.windows.{dom} needs start and end dates (YYYY-MM-DD), start before end")
    if enabled is True and not windows:
        errs.append("reserve.enabled is true but reserve.windows is empty: the fence must be set first")
    cap = get("exploration", "data_end")
    if cap is not None and _day(cap) is None:
        errs.append("exploration.data_end must be a date (YYYY-MM-DD)")
    if get("forward", "real_money") is not False:
        errs.append("forward.real_money must be false: Atlas builds no real-money execution")
    lc = get("forward", "loss_cap_usd")
    if lc is not None and (isinstance(lc, bool) or not isinstance(lc, (int, float)) or lc < 0):
        errs.append("forward.loss_cap_usd must be a number >= 0")
    end = get("programme", "end")
    if end is not None and _day(end) is None:
        errs.append("programme.end must be a date (YYYY-MM-DD) or null")
    for key, top in (("screening_fdr", SCREENING_FDR_MAX), ("forward_fdr", FORWARD_FDR_MAX)):
        v = get("levels", key)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 < v <= top):
            errs.append(f"levels.{key} must be in (0, {top}]: a looser level needs a new protocol version")
    claims, method = get("claims", "enabled"), get("claims", "screening_method")
    if claims not in (None, True, False):
        errs.append("claims.enabled must be true or false")
    if method not in SCREENING_METHODS:
        errs.append(f"claims.screening_method must be one of {SCREENING_METHODS[1:]} or null")
    if claims is True and method is None:
        errs.append("claims.enabled is true but claims.screening_method is null: the simulation chooses it first")
    if get("trial_ledger", "count_in_trials_csv") not in (None, True, False):
        errs.append("trial_ledger.count_in_trials_csv must be true or false")
    return errs


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["check"]:
        print(__doc__)
        return 2
    try:
        errs = validate(load())
    except (OSError, yaml.YAMLError) as e:
        errs = [f"config/atlas.yaml could not be read: {e}"]
    print("\n".join(errs) or "atlas config ok")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())

"""Append-only logs written by the night agents (on dev):

* results/exploration/log.csv: EVERY variant the explorer tests, kept or not (hard rule: log every variant). The
  data window must end on or before explorer.data_end (2019-12-31) in MAIN's config/night.yaml (read fresh through
  config.load_main, never the dev checkout's copy): a row reaching later is refused (exit 1); if main's cutoff
  cannot be read, nothing is logged (exit 2, "refused: cutoff unreadable").
* Inside the explorer's sandbox (Q019: ``.explore/sandbox.json`` and no ``.git``; see nightshift/explore_sandbox.py)
  a variant goes to ``.explore/out/variants.csv``, checked against the cutoff the sandbox was made with (main's at
  that time; there is no git there to fetch it). Those rows are provisional: ``explore_sandbox collect`` logs each
  one again through this module from the routine's own checkout, against main's cutoff fetched fresh.
* results/opposition/calibration.csv: The Opposition's probability (0-100) that a PR, queue item, idea or sleeve
  works, for later scoring (``outcome`` and ``resolved_on`` are filled when it resolves).

python -m nightshift.logs variant --hypothesis H... --variant V... --description ... --data-start YYYY-MM-DD
       --data-end YYYY-MM-DD --metric NAME --value X [--n-obs N] [--params JSON] [--code-ref PATH@SHA] [--nominated]
python -m nightshift.logs opposition --target-type pr|queue|idea|sleeve --target-id ID --p-works NN
       --verdict advisory|BLOCK-a..e --model MODEL [--note TEXT]
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime
from pathlib import Path

from . import config as C

EXPLORATION = C.ROOT / "results/exploration/log.csv"
CALIBRATION = C.ROOT / "results/opposition/calibration.csv"
EXP_COLS = ["logged_on", "hypothesis_id", "variant_id", "description", "data_start", "data_end", "n_obs", "metric",
            "value", "params", "code_ref", "nominated", "notes"]
CAL_COLS = ["logged_on", "target_type", "target_id", "p_works", "verdict", "model", "resolved_on", "outcome", "note"]
TARGETS = ("pr", "queue", "idea", "sleeve")
VERDICTS = ("advisory", "BLOCK-a", "BLOCK-b", "BLOCK-c", "BLOCK-d", "BLOCK-e")


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _append(path: Path, cols: list[str], row: dict) -> None:
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new:
            w.writeheader()
        w.writerow({c: row.get(c, "") for c in cols})


class CutoffUnreadable(RuntimeError):
    """main's explorer.data_end could not be read. Nothing is logged; the CLI exits 2 (not 1, over the cutoff)."""


SANDBOX_META = ".explore/sandbox.json"


def sandbox_meta() -> dict | None:
    """The sandbox's metadata when this module runs inside an explorer sandbox (bundle present, no .git), else None."""
    p = C.ROOT / SANDBOX_META
    if not p.is_file() or (C.ROOT / ".git").exists():
        return None
    import json
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CutoffUnreadable(f"{SANDBOX_META} unreadable: {e}") from e


def _default_log() -> Path:
    return C.ROOT / ".explore/out/variants.csv" if sandbox_meta() is not None else EXPLORATION


def main_cutoff() -> date:
    """explorer.data_end from main's protected config/night.yaml (C.load_main, fetched fresh), never from the
    checkout the explorer runs in (dev). Any failure raises CutoffUnreadable: there is no fallback. Inside a sandbox,
    the cutoff it was made with (provisional: collect checks every row again against main's)."""
    try:
        meta = sandbox_meta()
        v = meta["cutoff"] if meta is not None else C.load_main()["explorer"]["data_end"]
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, date):
            return v
        if not isinstance(v, str):
            raise TypeError(f"explorer.data_end is {v!r}")
        return date.fromisoformat(v)
    except Exception as e:  # noqa: BLE001 - every failure means the cutoff is unknown: refuse
        raise CutoffUnreadable(f"{type(e).__name__}: {e}") from e


def log_variant(row: dict, path: Path | None = None, data_end_max: str | None = None) -> dict:
    cap = main_cutoff()
    path = Path(path) if path is not None else _default_log()
    if data_end_max is not None:
        cap = min(cap, date.fromisoformat(data_end_max))   # can only tighten main's cutoff, never loosen it
    end, start = date.fromisoformat(row["data_end"]), date.fromisoformat(row["data_start"])
    if end > cap:
        raise ValueError(f"data_end {end} is after {cap}: exploration never uses 2020+ returns")
    if start > end:
        raise ValueError("data_start is after data_end")
    seen = _rows(path)
    if path != EXPLORATION and sandbox_meta() is not None:       # the sandbox's copy of dev's log counts too
        seen += _rows(C.ROOT / ".explore/exploration_log.csv")
    if any(r["variant_id"] == row["variant_id"] for r in seen):
        raise ValueError(f"variant {row['variant_id']} is already logged (variants are never overwritten)")
    row = {"logged_on": date.today().isoformat(), **row}
    _append(path, EXP_COLS, row)
    return row


def log_opposition(row: dict, path: Path = CALIBRATION) -> dict:
    p = float(row["p_works"])
    if not 0 <= p <= 100:
        raise ValueError("p_works must be 0-100")
    if row["target_type"] not in TARGETS:
        raise ValueError(f"target_type must be one of {TARGETS}")
    if row["verdict"] not in VERDICTS:
        raise ValueError(f"verdict must be one of {VERDICTS}")
    row = {"logged_on": date.today().isoformat(), **row, "p_works": f"{p:g}"}
    _append(path, CAL_COLS, row)
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("variant")
    for k in ("hypothesis", "variant", "description", "data-start", "data-end", "metric", "value"):
        v.add_argument(f"--{k}", required=True)
    v.add_argument("--n-obs", default="")
    v.add_argument("--params", default="")
    v.add_argument("--code-ref", default="")
    v.add_argument("--nominated", action="store_true")
    v.add_argument("--notes", default="")
    o = sub.add_parser("opposition")
    for k in ("target-type", "target-id", "p-works", "verdict", "model"):
        o.add_argument(f"--{k}", required=True)
    o.add_argument("--note", default="")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "variant":
            r = log_variant({"hypothesis_id": a.hypothesis, "variant_id": a.variant, "description": a.description,
                             "data_start": a.data_start, "data_end": a.data_end, "n_obs": a.n_obs,
                             "metric": a.metric, "value": a.value, "params": a.params, "code_ref": a.code_ref,
                             "nominated": "yes" if a.nominated else "", "notes": a.notes})
        else:
            r = log_opposition({"target_type": a.target_type, "target_id": a.target_id, "p_works": a.p_works,
                                "verdict": a.verdict, "model": a.model, "note": a.note})
    except CutoffUnreadable as e:
        print(f"refused: cutoff unreadable (main's config/night.yaml explorer.data_end): {e}")
        return 2
    except ValueError as e:
        print(f"refused: {e}")
        return 1
    print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())

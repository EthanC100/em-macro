"""Append-only logs written by the night agents (on dev):

* results/exploration/log.csv: EVERY variant the explorer tests, kept or not (hard rule: log every variant). The
  data window must end on or before config explorer.data_end (2019-12-31): a row reaching later is refused.
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
from datetime import date
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


def log_variant(row: dict, path: Path = EXPLORATION, data_end_max: str | None = None) -> dict:
    cap = date.fromisoformat(data_end_max or C.load()["explorer"]["data_end"])
    end, start = date.fromisoformat(row["data_end"]), date.fromisoformat(row["data_start"])
    if end > cap:
        raise ValueError(f"data_end {end} is after {cap}: exploration never uses 2020+ returns")
    if start > end:
        raise ValueError("data_start is after data_end")
    if any(r["variant_id"] == row["variant_id"] for r in _rows(path)):
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
    except ValueError as e:
        print(f"refused: {e}")
        return 1
    print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())

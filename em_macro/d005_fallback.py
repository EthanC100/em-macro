"""D005 fail-safe: book v1.0 unadjusted for the month when the D005 step fails. Standard library only.

    python -m em_macro.d005_fallback     # systematic-monthly, only if the D005 step failed

`python -m em_macro.d005 update` handles its own errors: it books the current month unadjusted, keeps the D005 P&L
of months already booked, writes results/systematic/d005/status.json and exits 1, so the workflow raises its alert
while v1.0 still rebalances and is committed. This module covers the case where that process died before writing
paper_pnl.csv (for example an import error), so it imports nothing from em_macro.d005, pandas or numpy:

* paper_pnl.csv still holds the overlay step's output (no ``d005_adj`` column). The D005 P&L of months already booked
  is carried forward from the last committed paper_pnl.csv (``git show HEAD:``), ``net_before_d005`` = model_net +
  override_pnl, ``final_net`` = net_before_d005 + d005_adj, ``cumulative_final`` recomputed. The month just completed
  keeps its committed value if it had one, else 0 (unadjusted).
* The current month's rows are removed from results/systematic/d005/weights.csv and positions.csv, so this month's
  book is v1.0's (unadjusted) everywhere: the Ledger shows v1.0's sizes and later P&L uses v1.0's weights.
* results/systematic/d005/status.json records the failure.

If paper_pnl.csv already has ``d005_adj``, em_macro.d005 wrote its own fail-safe result; only the current month's
D005 rows are checked against status.json. v1.0's own files are never touched.
"""
from __future__ import annotations

import csv
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYS = "results/systematic"
PAPER_PNL = f"{SYS}/paper_pnl.csv"
V10_POSITIONS = f"{SYS}/positions.csv"
D005_DIR = f"{SYS}/d005"
WEIGHTS, POSITIONS, STATUS = f"{D005_DIR}/weights.csv", f"{D005_DIR}/positions.csv", f"{D005_DIR}/status.json"


def _read(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    os.replace(tmp, path)


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def committed_d005_adj(root: Path = ROOT, ref: str = "HEAD") -> dict[str, float]:
    """month -> d005_adj in the last committed paper_pnl.csv ({} if it has none or git is unavailable)."""
    try:
        txt = subprocess.run(["git", "show", f"{ref}:{PAPER_PNL}"], cwd=root, capture_output=True, text=True,
                             check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return {}
    rows = list(csv.DictReader(io.StringIO(txt)))
    return {r["month"]: _num(r.get("d005_adj")) for r in rows if r.get("d005_adj") not in (None, "")}


def current_as_of(root: Path = ROOT) -> str | None:
    _, rows = _read(root / V10_POSITIONS)
    return rows[0].get("as_of") if rows else None


def drop_month(root: Path, as_of: str | None) -> list[str]:
    """Remove the current month's D005 rows (weights and book): the month books v1.0 unadjusted."""
    done = []
    for rel in (WEIGHTS, POSITIONS):
        cols, rows = _read(root / rel)
        keep = [r for r in rows if r.get("as_of") != as_of]
        if cols and len(keep) != len(rows):
            _write(root / rel, cols, keep)
            done.append(rel)
    return done


def carry_forward(root: Path = ROOT, carried: dict[str, float] | None = None) -> int:
    """Add the D005 columns to an overlay-only paper_pnl.csv from the committed values. Returns the months adjusted."""
    cols, rows = _read(root / PAPER_PNL)
    carried = committed_d005_adj(root) if carried is None else carried
    cum, n = 1.0, 0
    for r in rows:
        base = _num(r.get("model_net") if r.get("model_net") not in (None, "") else r.get("net")) + _num(r.get("override_pnl"))
        adj = carried.get(r["month"], 0.0)
        n += adj != 0.0
        final = base + adj
        cum *= 1 + final
        r["net_before_d005"], r["d005_adj"] = f"{base:.6f}", f"{adj:.6f}"
        r["final_net"], r["cumulative_final"] = f"{final:.6f}", f"{cum:.6f}"
    for c in ("net_before_d005", "d005_adj", "final_net", "cumulative_final"):
        if c not in cols:
            cols.append(c)
    _write(root / PAPER_PNL, cols, rows)
    return n


def run(root: Path = ROOT, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc).replace(microsecond=0)
    as_of = current_as_of(root)
    cols, _ = _read(root / PAPER_PNL)
    status_path = root / STATUS
    prev = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    out = {"decision": "D005", "as_of": as_of, "status": "failed", "applied": False,
           "booked": "v1.0 unadjusted for this month (fail-safe)", "evaluated_at": now.isoformat().replace("+00:00", "Z")}
    if "d005_adj" in cols and prev.get("as_of") == as_of and prev.get("status") == "failed":
        out.update({k: prev[k] for k in ("errors", "pnl_source") if k in prev})
        out["fallback"] = "em_macro.d005 wrote its own fail-safe result; nothing to carry forward"
    else:
        n = carry_forward(root) if "d005_adj" not in cols else None
        out["errors"] = prev.get("errors", []) if prev.get("as_of") == as_of else []
        out["errors"].append("em_macro.d005 update stopped before writing its result (see the workflow log)")
        out["fallback"] = ("em_macro.d005_fallback carried forward the committed D005 P&L "
                           f"({n} month(s) with a non-zero adjustment)" if n is not None else
                           "paper_pnl.csv already had D005 columns; left as written")
        out["pnl_source"] = "committed paper_pnl.csv (HEAD)"
    out["dropped"] = drop_month(root, as_of)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return out


def main() -> int:
    res = run()
    print(f"D005 fail-safe: {res['booked']} (as of {res['as_of']}); {res['fallback']}; dropped {res['dropped'] or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Command line of the operations app.

    python -m manhattan.app build --batches DIR [--ledger-clone DIR | --remote PATH] --out DIR
    python -m manhattan.app demo --out DIR [--workdir DIR]

``build`` reads frozen batch folders and, optionally, the private ledger: an existing clone read from disk without
git (``--ledger-clone``), or a remote cloned read-only into a temporary directory (``--remote``). Nothing is ever
written to the ledger. ``demo`` builds a fully synthetic batch and ledger (no network, no real ledger) in a temporary
directory, or in ``--workdir`` when given (kept), and renders it. Both write ``index.html`` and ``view.json``.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import model as M
from . import render


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build(batches: Path, out: Path, *, ledger_clone: Path | None = None, remote: str | None = None,
          generated_utc: str | None = None) -> dict:
    if ledger_clone and remote:
        raise ValueError("give --ledger-clone or --remote, not both")
    with tempfile.TemporaryDirectory(prefix="manhattan-app-") as tmp:
        ledger = None
        if ledger_clone:
            ledger = M.ReadOnlyLedger(Path(ledger_clone))
        elif remote:
            from manhattan.ops import store as ST
            ledger = ST.Store(workdir=Path(tmp) / "ledger", remote=str(remote)).open()   # read only: never written
        view = M.build_view(Path(batches), ledger, generated_utc=generated_utc or _now())
    return {"view": view, **render.write(view, Path(out))}


def demo(out: Path, workdir: Path | None = None, generated_utc: str | None = None) -> dict:
    from . import demo as DM

    def go(wd: Path) -> dict:
        d = DM.run(wd)
        res = build(d["batches"], out, remote=str(d["remote"]), generated_utc=generated_utc or _now())
        return {**res, "demo": d}

    if workdir is not None:
        return go(Path(workdir))
    with tempfile.TemporaryDirectory(prefix="manhattan-app-demo-") as tmp:
        return go(Path(tmp) / "demo")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.app", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build the page from frozen batches and, optionally, the private ledger")
    b.add_argument("--batches", required=True, help="folder holding AB-NNNN batch folders")
    g = b.add_mutually_exclusive_group()
    g.add_argument("--ledger-clone", help="an existing clone of the private ledger (read from disk, never written)")
    g.add_argument("--remote", help="the private ledger's git remote (cloned read-only into a temporary folder)")
    b.add_argument("--out", required=True)
    d = sub.add_parser("demo", help="build a fully synthetic demo (no network, no real ledger)")
    d.add_argument("--out", required=True)
    d.add_argument("--workdir", help="keep the synthetic batch and ledger here (an empty or new folder)")
    a = ap.parse_args(argv)
    if a.cmd == "build":
        res = build(Path(a.batches), Path(a.out), ledger_clone=Path(a.ledger_clone) if a.ledger_clone else None,
                    remote=a.remote)
    else:
        res = demo(Path(a.out), Path(a.workdir) if a.workdir else None)
    c = res["view"]["counts"]
    print(f"wrote {res['html']} and {res['json']}: {c['families']} families, {c['hypotheses']} hypotheses, "
          f"{c['unique_executable_configurations']} executable configurations, "
          f"{c['registered_predictions']} registered predictions"
          + (", SYNTHETIC DEMO" if res["view"]["synthetic"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

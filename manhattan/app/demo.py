"""A fully synthetic demo: a mock batch AB-0001, a local bare-repository ledger, registration and nightly runs.

The flow is the one ``tests/test_manhattan_ops_e2e.py`` proves (``flow``), without the crash and failure cases:
ten SYNTHETIC families from the mock generator (no model), exploration screening on synthetic data recorded in the
private ledger stand-in, ``freeze_pr.prepare`` into a batches folder, one capture-only night, registration with a
fixed merge time and witness, then nightly runs on fixed dates with a fake clock. Family 4 declares a first
observation before the merge, so its predictions are registered as ineligible (tracked, weight 0).

Nothing touches the network (the synthetic source is generated in memory) or any real ledger (the remote is a bare
repository created inside the work directory). Forward attempts record the repository's HEAD as their code
identity, because the runner verifies ``config/manhattan.yaml`` at that commit (D-12).
"""
from __future__ import annotations

import contextlib
import io
import subprocess
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NIGHTS = (date(2026, 11, 16), date(2026, 11, 17))     # after the capture-only night of 12 November
LATE = {3: "2026-11-12"}                               # family 4: a first observation the day before the merge


class Clock:
    """A fixed fake clock: set with ``at``, one second per call."""

    def __init__(self):
        self.t = None

    def at(self, s: str) -> None:
        from manhattan.ops import timing as TM
        self.t = TM.parse_time(s)

    def __call__(self):
        self.t += timedelta(seconds=1)
        return self.t


def _git(*a, cwd: Path) -> str:
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout


def repo_head() -> str:
    """The checked-out commit of this repository (the configuration pin of forward runs is verified at it)."""
    return _git("rev-parse", "HEAD", cwd=ROOT).strip()


def run(workdir: Path, nights: tuple = NIGHTS) -> dict:
    """Build the synthetic batch and ledger under ``workdir`` (created; must not exist or be empty). Returns the
    paths: ``batches`` (frozen batch folders), ``remote`` (the bare-repository ledger) and ``log`` (the runs' public
    health lines, kept out of the console)."""
    from manhattan import config as MC
    from manhattan import roles
    from manhattan.engine.pit import PitStore
    from manhattan.generate import parse_reply
    from manhattan.ops import compiler as CP
    from manhattan.ops import data as D
    from manhattan.ops import freeze_pr, mockgen
    from manhattan.ops import runner as R
    from manhattan.ops import store as ST
    from manhattan.ops import timing as TM

    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    if any(workdir.iterdir()):
        raise FileExistsError("the demo work directory must be empty")
    head = repo_head()
    clock = Clock()
    log = io.StringIO()
    req = mockgen.blind_request(n_families=10, max_hypotheses=2, domains=("syn_daily",))
    fams, hyps = parse_reply(mockgen.mock_reply(req, declared=LATE), "blind")
    remote = workdir / "manhattan-ledger.git"
    _git("init", "-q", "--bare", "-b", "main", str(remote), cwd=workdir)

    with contextlib.redirect_stdout(log):
        # exploration screening on labelled synthetic data to 2019-12-31, recorded privately (weight 0)
        clock.at("2026-11-12T12:00:00Z")
        exes = list(CP.iter_batch(fams, hyps, "c" * 40))
        pit = PitStore()
        by: dict = {}
        for s_, p_, v_ in D.synthetic_rows(date(2019, 12, 31)):
            by.setdefault(s_, ([], []))
            by[s_][0].append(p_)
            by[s_][1].append(v_)
        for s_, (ps, vs) in by.items():
            pit.add(s_, ps, vs, lag_days=0 if "px" in s_ or "evt" in s_ else 1)
        fence = roles.Fence.from_config(MC.load())
        sc = ST.Store(workdir=workdir / "rt-screen/private/ledger", remote=str(remote), run_id="900",
                      commit="c" * 40, clock=clock).open()
        returns = R.screen(sc, exes, pit, fence, date(2015, 1, 2), date(2019, 12, 31))

        # the freeze tooling writes the batch folder (the owner's merge is simulated below)
        batches = workdir / "public/data/manhattan/batches"
        prep = freeze_pr.prepare(1, fams, hyps, out_root=batches, code_version="c" * 40,
                                 protocol_path=ROOT / "docs/manhattan/PROTOCOL_v3.md",
                                 generator_model="mock-no-model", template_hash=req.template_hash, fence={},
                                 screening_returns=returns)
        del returns                                          # in memory only, never written

        def cfg(asof: date, run_id: int) -> R.RunConfig:
            return R.RunConfig(ledger_dir=workdir / f"rt{run_id}/private/ledger", remote=str(remote),
                               batches_dir=batches, asof=asof, sources=("synthetic",), run_id=str(run_id),
                               commit=head, private_dir=workdir / f"rt{run_id}/private", run_calendar="synthetic")

        def fetch(a: date) -> dict:
            return {"synthetic": (lambda: D.synthetic_csv(a))}

        healths = []
        clock.at("2026-11-12T23:30:00Z")                     # capture only: nothing registered yet
        healths.append(R.nightly(cfg(date(2026, 11, 12), 101), fetch(date(2026, 11, 12)), clock=clock))
        clock.at("2026-11-13T16:45:00Z")                     # merged 15:00, witnessed 16:30 (stand-ins)
        pr = {"merged": True, "merged_at": "2026-11-13T15:00:00Z", "merge_commit_sha": "d" * 40}
        w = TM.Witness("opentimestamps", prep["manifest_hash"], TM.parse_time("2026-11-13T16:30:00Z"), True)
        healths.append(R.register(cfg(date(2026, 11, 13), 102), 1, pr, w, clock=clock))
        for i, night in enumerate(nights):                   # the Friday night (13th) run never happens: missed
            clock.at(f"{night.isoformat()}T23:30:00Z")
            healths.append(R.nightly(cfg(night, 103 + i), fetch(night), clock=clock))
    return {"workdir": workdir, "batches": batches, "remote": remote, "manifest_hash": prep["manifest_hash"],
            "healths": healths, "log": log.getvalue()}

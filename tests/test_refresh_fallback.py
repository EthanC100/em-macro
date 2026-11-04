"""Monthly-refresh fallback, end to end, without network.

What the monthly workflow (systematic.yml) does: restore the previous run's raw downloads from the
Actions cache into data/raw, run ``python -m em_macro.systematic refresh 2>&1 | tee refresh.log`` with
EM_MACRO_REFRESH=1 under ``bash -eo pipefail``, and, if a step fails, run the "Open or update the alert
issue" step, which calls ``gh issue create``.

How it is simulated here (approximations, since neither the Actions cache nor GitHub is available):
- the Actions cache is a directory of last month's raw files that is copied into a temporary RAW
  directory, as actions/cache/restore does into data/raw;
- a failed download is a stubbed HTTP session: mindicador.cl answers 502 (the 3 Nov 2026 failure),
  FRED raises a connection error, BIS answers 200 with an HTML page; yfinance returns empty frames;
  retries' sleeps are skipped;
- the refresh runs in a subprocess under ``bash -eo pipefail -c '... 2>&1 | tee refresh.log'``, like
  the workflow step. With the cache present, the three builders of ``stage_refresh`` are replaced by
  one that calls the real loaders for the series v1.0's ``build_inputs`` downloads directly (FRED,
  BIS policy rates and CPI, BanRep TRM, BCCh via mindicador.cl) and writes them to PROC: the full
  refresh needs every source's cache (gigabytes, incl. Tesouro and BondSpot), which a unit test
  cannot carry. Without a cache the real ``stage_refresh`` runs and fails on its first download;
- the alert is the workflow's own alert-step script, read from systematic.yml and run by bash with a
  stub ``gh`` on PATH that records its arguments.
"""
import json
import os
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime, timezone

import pandas as pd
import pytest
import yaml

from em_macro.config import ROOT

DRIVER = textwrap.dedent('''
    """Run ``python -m em_macro.systematic refresh`` with RAW/PROC redirected and the network failing."""
    import os, runpy, sys
    from pathlib import Path
    import pandas as pd
    import requests
    raw, proc, mode = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    import em_macro.build_data, em_macro.panel, em_macro.risk_model   # not systematic: runpy runs it fresh
    from em_macro import sources as S, panel_sources as PS
    for m in [m for k, m in sys.modules.items() if k.startswith("em_macro")]:
        if hasattr(m, "RAW"): m.RAW = raw
        if hasattr(m, "PROC"): m.PROC = proc

    class R:
        def __init__(self, status, content=b""):
            self.status_code, self.content, self.reason, self.headers = status, content, "x", {}

    def get(url, timeout=None):
        if "mindicador.cl" in url: return R(502)                  # the 3 Nov 2026 failure
        if "stats.bis.org" in url: return R(200, b"<html>Service Unavailable</html>")
        raise requests.ConnectionError(f"simulated outage: {url}")
    S.SESSION.get = get
    S.time.sleep = lambda s: None
    import yfinance as yf
    yf.download = lambda *a, **k: pd.DataFrame()

    if mode == "loaders":           # the series build_inputs() downloads directly
        def build(refresh=False):
            out = {"DFF": S.fred("DFF", refresh), "policy_BR": S.bis_policy("BR", refresh),
                   "cpi_US": PS.bis_cpi_index("US", refresh), "trm": PS.colombia_trm(refresh),
                   "clp": PS.chile_dolar_observado(refresh)}
            proc.mkdir(parents=True, exist_ok=True)
            for k, s in out.items():
                s.to_csv(proc / f"{k}.csv")
        em_macro.build_data.build = build
        em_macro.panel.build = lambda: None
        em_macro.risk_model.build_data = lambda: None
    sys.argv = ["systematic", "refresh"]
    runpy.run_module("em_macro.systematic", run_name="__main__")
''')

THIS_YEAR = pd.Timestamp.today().year


def _actions_cache(d):
    """Last month's raw downloads, as the previous run saved them."""
    files = {
        "fred/DFF.csv": "observation_date,DFF\n2026-09-30,4.08\n2026-10-31,3.87\n",
        "bis/CBPOL_BR.csv": "FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\nD,BR,2026-09-30,15.0\nD,BR,2026-10-31,15.0\n",
        "bis/CPIIDX_US.csv": "FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\nM,US,2026-08,330.1\nM,US,2026-09,331.0\n",
        "colombia/trm.json": json.dumps([{"valor": "3870.5", "vigenciadesde": "2026-10-31T00:00:00.000"}]),
    }
    for y in range(2004, THIS_YEAR + 1):
        files[f"chile/dolar_{y}.json"] = json.dumps({"serie": [{"fecha": f"{y}-06-30T04:00:00.000Z", "valor": 900.0 + y - 2004}]})
    for rel, body in files.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(body)
    return d


def _refresh(tmp_path, mode):
    """The workflow's refresh step: python ... refresh 2>&1 | tee refresh.log, under bash -eo pipefail."""
    driver = tmp_path / "driver.py"
    driver.write_text(DRIVER)
    runner_temp = tmp_path / "runner"
    runner_temp.mkdir(exist_ok=True)
    env = {**os.environ, "EM_MACRO_REFRESH": "1", "PYTHONPATH": str(ROOT), "RUNNER_TEMP": str(runner_temp)}
    cmd = f'"{sys.executable}" "{driver}" "{tmp_path / "raw"}" "{tmp_path / "proc"}" {mode} 2>&1 | tee "$RUNNER_TEMP/refresh.log"'
    p = subprocess.run(["bash", "-eo", "pipefail", "-c", cmd], env=env, capture_output=True, text=True, cwd=tmp_path,
                       timeout=600)
    return p.returncode, (runner_temp / "refresh.log").read_text(), runner_temp


def _workflow_step(name):
    wf = yaml.safe_load((ROOT / ".github/workflows/systematic.yml").read_text())
    return next(s for s in wf["jobs"]["update"]["steps"] if s.get("name") == name)


def test_refresh_completes_from_the_actions_cache_with_warnings(tmp_path):
    shutil.copytree(_actions_cache(tmp_path / "actions-cache"), tmp_path / "raw")       # cache restore
    code, log, _ = _refresh(tmp_path, "loaders")
    assert code == 0, log
    warnings = [l for l in log.splitlines() if l.startswith("WARNING:")]
    for src in ("fredgraph.csv?id=DFF", "WS_CBPOL/D.BR", "WS_LONG_CPI/M.US", "datos.gov.co",
                f"mindicador.cl/api/dolar/{THIS_YEAR}"):
        assert any(src in w and "using the cached copy" in w for w in warnings), (src, log)
    assert any("HTTP 502" in w for w in warnings) and any("simulated outage" in w for w in warnings)
    # the refreshed outputs are last month's cached values
    dff = pd.read_csv(tmp_path / "proc" / "DFF.csv", index_col=0)
    assert list(dff.iloc[:, 0]) == [4.08, 3.87]
    clp = pd.read_csv(tmp_path / "proc" / "clp.csv", index_col=0)
    assert len(clp) == THIS_YEAR - 2004 + 1
    # the failed downloads did not overwrite the cache
    assert (tmp_path / "raw/fred/DFF.csv").read_text() == (tmp_path / "actions-cache/fred/DFF.csv").read_text()


def test_refresh_without_cache_fails_cleanly_and_opens_an_alert(tmp_path):
    (tmp_path / "raw").mkdir()                                       # no Actions cache to restore
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "daily_panel.csv").write_text("last month's panel\n")
    code, log, runner_temp = _refresh(tmp_path, "full")               # the real stage_refresh
    # fails: non-zero exit through the pipe, a clear error, nothing written
    assert code != 0
    assert "RuntimeError: download failed: https://fred.stlouisfed.org/" in log
    assert (proc / "daily_panel.csv").read_text() == "last month's panel\n"
    assert sorted(p.name for p in proc.iterdir()) == ["daily_panel.csv"]
    assert not [p for p in (tmp_path / "raw").rglob("*") if p.is_file()]          # no bad body cached

    # the workflow's alert step, run as on the runner with a stub gh
    step = _workflow_step("Open or update the alert issue")
    assert step["if"].startswith("failure()")          # or a v1.1 step failed (continue-on-error; tests/test_v11.py)
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    calls = tmp_path / "gh_calls.txt"
    (bin_ / "gh").write_text(textwrap.dedent(f'''\
        #!/usr/bin/env bash
        echo "gh $*" >> "{calls}"
        prev=""
        for a in "$@"; do
          if [ "$prev" = "--body-file" ]; then cp "$a" "{tmp_path}/issue_body.md"; fi
          prev="$a"
        done
        exit 0
    '''))
    (bin_ / "gh").chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "GH_TOKEN": "x", "RUNNER_TEMP": str(runner_temp),
           "GITHUB_REPOSITORY": "owner/em-macro", "RUN_URL": "https://github.com/owner/em-macro/actions/runs/1",
           "RUN_ATTEMPT": "1",
           "OUTCOMES": "install=success refresh=failure update=skipped rebalance=skipped overlay=skipped "
                       "tests=skipped commit=skipped"}
    p = subprocess.run(["bash", "-eo", "pipefail", "-c", step["run"]], env=env, capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    created = [l for l in calls.read_text().splitlines() if l.startswith("gh issue create")]
    assert len(created) == 1
    assert f"--title [ALERT] systematic-monthly failed {today}" in created[0] and "--label alert" in created[0]
    body = (tmp_path / "issue_body.md").read_text()
    assert "**Failing step:** Refresh data" in body and "download failed" in body

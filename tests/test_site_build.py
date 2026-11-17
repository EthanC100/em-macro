"""The Ledger site builds as the ledger-pages workflow builds it (2026-11-17, docs/config_changes.md).

From 11 to 17 Nov 2026 every ledger-pages run failed (``ModuleNotFoundError: No module named 'yaml'``: C09 put
``import yaml`` in the build path) and the published site stayed at 11 Nov, while this suite stayed green: it runs
with every package of requirements.txt installed, and the pages job installed none. These tests build the site with
only the standard library and requirements-site.txt importable (ledger/site_check.py), and check that the workflow
installs exactly that file before it builds, so the two environments cannot drift apart again.

The build reads the frozen copies of the writers' files (tests/fixtures/live, Q025), never the live ones: a data
change by ledger-daily or systematic-monthly can never fail this test and block their commits. The night shift's
promote check (e) builds the live merged tree the same way.
"""
import json
import shutil
from datetime import date
from pathlib import Path

import yaml

from conftest import ROOT, make_frozen_repo
from ledger import site_check as SC

TODAY = date(2026, 11, 12)          # the frozen copies were taken from main on 12 Nov 2026


def _pages_build_job() -> dict:
    wf = yaml.safe_load((ROOT / ".github/workflows/ledger-pages.yml").read_text(encoding="utf-8"))
    return wf["jobs"]["build"]


def test_workflow_installs_exactly_requirements_site_before_building():
    steps = [s.get("run", "") for s in _pages_build_job()["steps"]]
    i_build = next(i for i, r in enumerate(steps) if "python -m ledger.build" in r)
    installs = [r.strip() for r in steps[:i_build] if "pip install" in r]
    assert installs == ["pip install -r requirements-site.txt"], installs
    # the site's requirements are part of the full set, so every other session and job has them too
    full = {SC._norm(n) for n in SC.requirement_names(ROOT / "requirements.txt")}
    site = {SC._norm(n) for n in SC.requirement_names(ROOT / "requirements-site.txt")}
    assert site and site <= full, site - full


def _fake_root(tmp_path: Path, imports: str) -> Path:
    root = tmp_path / "repo"
    (root / "ledger").mkdir(parents=True)
    (root / "ledger/__init__.py").write_text("")
    (root / "ledger/build.py").write_text(f"{imports}\nimport sys\nprint('built', sys.argv[1:])\n")
    return root


def test_site_check_sees_only_the_site_requirements(tmp_path):
    """The check's environment is the pages runner's: a package installed here but not in requirements-site.txt
    (pandas, the C09 case with yaml) is missing, exactly as on the runner."""
    none = tmp_path / "none.txt"
    none.write_text("# nothing\n")
    yaml_only = tmp_path / "yaml.txt"
    yaml_only.write_text("pyyaml>=6.0\n")
    r = SC.build_like_pages(_fake_root(tmp_path / "a", "import yaml"), requirements=none)
    assert not r["ok"] and "No module named 'yaml'" in r["detail"], r
    r = SC.build_like_pages(_fake_root(tmp_path / "b", "import yaml"), requirements=yaml_only)
    assert r["ok"], r
    r = SC.build_like_pages(_fake_root(tmp_path / "c", "import pandas"), requirements=yaml_only)
    assert not r["ok"] and "No module named 'pandas'" in r["detail"], r


def test_site_builds_with_only_its_requirements(tmp_path):
    """The real build, on the frozen mirror, in the pages environment. The mirror links the code; the packages are
    copied so that the build's ROOT (its __file__, resolved) is the mirror and it reads the frozen files."""
    root = make_frozen_repo(tmp_path / "em-macro")
    for e in list(root.iterdir()):
        if e.is_symlink() and e.is_dir() and (e / "__init__.py").exists():
            src = e.resolve()
            e.unlink()
            shutil.copytree(src, e, ignore=shutil.ignore_patterns("__pycache__"))
    out = tmp_path / "app"
    r = SC.build_like_pages(root, out, TODAY.isoformat())
    assert r["ok"], r["detail"]
    meta = json.loads((out / "data/meta.json").read_text())
    assert meta["today"] == TODAY.isoformat() and (out / "index.html").exists()

    # the frozen marks hold CLP 2026-11-30 (fetched 11 Nov): the site never shows a mark after its day
    assert meta["sources"]["latest_mark"] and meta["sources"]["latest_mark"] <= TODAY.isoformat(), meta["sources"]
    marks = json.loads((out / "data/marks.json").read_text())
    assert marks["summary"]["last_date"] <= TODAY.isoformat(), marks["summary"]
    assert all((i["date"] or "") <= TODAY.isoformat() for i in marks["items"]), \
        [(i["instrument"], i["date"]) for i in marks["items"] if (i["date"] or "") > TODAY.isoformat()]


def test_promote_refuses_when_the_site_does_not_build(tmp_path, monkeypatch):
    """Promote check (e): the merged tree's ``python -m ledger.site_check`` failing blocks the promotion, with the
    build's last error line as the reason (everything else passes)."""
    import subprocess

    from nightshift import promote as PR

    def g(*a):
        subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True,
                       env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                            "GIT_COMMITTER_EMAIL": "t@t", "PATH": "/usr/bin:/bin"})
    repo = tmp_path / "r"
    repo.mkdir()
    g("init", "-q", "-b", "main")
    (repo / ".github").mkdir()
    (repo / ".github/CODEOWNERS").write_text("# protected:start\n/trials.csv @E\n# protected:end\n")
    (repo / "a.txt").write_text("1\n")
    g("add", "-A")
    g("commit", "-q", "-m", "base")
    g("checkout", "-q", "-b", "dev")
    (repo / "b.txt").write_text("x\n")
    g("add", "-A")
    g("commit", "-q", "-m", "Merge Q003: b")
    g("checkout", "-q", "main")
    monkeypatch.setattr(PR, "build_ledger", lambda tree, out, today, store: (out / "data").mkdir(parents=True) or {"ok": True, "detail": ""})
    real_sh, calls = PR.sh, []

    def sh(args, cwd, env=None, timeout=0):
        if args[0] == "git":
            return real_sh(args, cwd, env=env)
        calls.append(args[1:3])
        if args[1:3] == ["-m", "ledger.site_check"]:
            out = json.dumps({"ok": False, "detail": "Traceback ...\nModuleNotFoundError: No module named 'yaml'"})
            return subprocess.CompletedProcess(args, 1, out, "")
        return subprocess.CompletedProcess(args, 0, "1 passed", "")
    monkeypatch.setattr(PR, "sh", sh)
    res = PR.run(repo, "main", "dev", "2026-11-17", None, run_tests=True, work=tmp_path)
    assert ["-m", "ledger.site_check"] in calls
    assert res["checks"]["a_tests"]["ok"] and res["checks"]["b_ledger_rebuild"]["ok"]
    assert not res["checks"]["e_site_build"]["ok"] and not res["ok"]
    assert PR.reasons(res) == ["(e) site does not build as ledger-pages builds it: "
                               "ModuleNotFoundError: No module named 'yaml'"]

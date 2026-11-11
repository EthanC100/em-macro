"""Q019: exploration reads data only through one loader (nightshift/explore_data.py) that serves a frozen extract
truncated at MAIN's explorer.data_end, verified against a manifest read from origin/main (never the dev checkout),
and the guard keeps night-explorer off until main has that manifest and its CODEOWNERS block protects the loader,
the extract, the manifest and nightshift/logs.py.

Synthetic fixtures only: C.load_main is monkeypatched (never the live config/night.yaml), git runs on temporary
repositories with a bare origin (never the real remote), the Actions API, state and queue are stubbed, and every
build writes under tmp_path. No real data file is read and no real extract is built."""
from __future__ import annotations

import ast
import csv
import hashlib
import importlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from nightshift import config as C
from nightshift import guard as G
from nightshift import queue as Q
from nightshift import state as S

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures/night/night.yaml"
NOW = "2026-11-09T23:40:00+08:00"          # inside the chain window, no busy window
MANIFEST, EXTRACT = "data/exploration/manifest.json", "data/exploration/extract.csv"
MUST_PROTECT = ("nightshift/explore_data.py", MANIFEST, EXTRACT, "nightshift/logs.py")
FULL_BLOCK = "/nightshift/explore_data.py @E\n/data/exploration/ @E\n/nightshift/logs.py @E\n"


def _ed():
    """The loader module (absent before Q019: those tests fail on the import)."""
    return importlib.import_module("nightshift.explore_data")


def _cfg(data_end="2019-12-31", hyp=3) -> dict:
    c = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    c["safe_mode"]["enabled"] = False
    c["explorer"] = {"max_hypotheses_per_night": hyp, "data_end": data_end}
    return c


@pytest.fixture
def main_cfg(monkeypatch):
    """main's config (data_end 2019-12-31); the dev checkout's copy is loosened to 2021 and must never be used."""
    box = {"cfg": _cfg()}

    def load_main(*a, **k):
        if isinstance(box["cfg"], Exception):
            raise box["cfg"]
        return box["cfg"]
    monkeypatch.setattr(C, "load_main", load_main)
    monkeypatch.setattr(C, "load", lambda *a, **k: _cfg("2021-12-31"))
    return box


# ------------------------------------------------------------------------------------------------ git fixtures
def _git(cwd: Path, *a: str) -> str:
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main", *a],
                       cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


class Repos:
    """A bare origin, a clone where 'main' commits are made (as Ethan would), and a dev checkout (the explorer's)."""

    def __init__(self, tmp: Path):
        self.origin, self.main, self.dev = tmp / "origin.git", tmp / "main_wt", tmp / "dev_wt"
        _git(tmp, "init", "-q", "--bare", str(self.origin))
        _git(tmp, "clone", "-q", str(self.origin), str(self.main))
        _git(self.main, "checkout", "-q", "-b", "main")
        (self.main / "README").write_text("fixture\n")
        self.codeowners("/docs/prereg/ @E\n")
        _git(self.main, "add", "-A")
        _git(self.main, "commit", "-q", "-m", "base")
        _git(self.main, "push", "-q", "origin", "main")
        _git(tmp, "clone", "-q", str(self.origin), str(self.dev))
        _git(self.dev, "checkout", "-q", "-b", "dev")

    def codeowners(self, block: str) -> None:
        p = self.main / ".github/CODEOWNERS"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# header\n# protected:start\n{block}# protected:end\n/other/ @E\n")

    def push_main(self, msg: str) -> None:
        _git(self.main, "add", "-A")
        _git(self.main, "commit", "-q", "-m", msg)
        _git(self.main, "push", "-q", "origin", "main")

    def sync_dev(self) -> None:
        _git(self.dev, "fetch", "-q", "origin")
        _git(self.dev, "merge", "-q", "--no-edit", "origin/main")


@pytest.fixture
def repos(tmp_path):
    return Repos(tmp_path)


# ------------------------------------------------------------------------------------------- synthetic sources
PRE = [("2019-12-26", "1.0", "5.0"), ("2019-12-27", "1.5", ""), ("2019-12-30", "2.0", "5.5"),
       ("2019-12-31", "2.5", "6.0")]


def _write_sources(root: Path) -> None:
    """Two public-looking synthetic files; rows after 2019-12-31 are poison: unconvertible values, then lines that
    are not even CSV dates. A third file in the same folder is NOT on the allowlist."""
    (root / "src").mkdir(parents=True, exist_ok=True)
    lines = ["date,level,extra_unlisted"] + [f"{d},{a},{b}" for d, a, b in PRE]
    lines += ["2020-01-02,BOOM,BOOM", "2020-03-31,NaN-not-a-number,x", "garbage line,\"unterminated", "zz,1,2"]
    (root / "src/a.csv").write_text("\n".join(lines) + "\n")
    (root / "src/b.csv").write_text("obs_date,rate\n2019-11-29,3.25\n2019-12-31,3.5\n2020-01-31,BOOM\n")
    (root / "src/not_listed.csv").write_text("date,secret\n2019-01-01,1\n2021-01-01,2\n")


def _manifest(**over) -> dict:
    m = {"note": "synthetic fixture",
         "sources": [
             {"id": "srcA", "path": "src/a.csv", "source": "Synthetic public statistic A (test fixture)",
              "licence": "public domain (fixture)", "date_column": "date",
              "columns": [{"column": "level", "series": "a_level", "point_in_time": True}]},
             {"id": "srcB", "path": "src/b.csv", "source": "Synthetic central bank rate B (test fixture)",
              "licence": "public, free reuse with attribution (fixture)", "date_column": "obs_date",
              "columns": [{"column": "rate", "series": "b_rate", "point_in_time": True}]}]}
    m.update(over)
    return m


def _build_into(ED, root: Path, manifest: dict | None = None) -> dict:
    _write_sources(root)
    mp = root / MANIFEST
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(manifest or _manifest(), indent=1))
    return ED.build(mp, src_root=root, out_dir=root / "data/exploration")


def _ready_main(ED, repos: Repos, block: str = FULL_BLOCK) -> None:
    """main gets a built manifest and extract, the loader and logs.py stand-ins, and a CODEOWNERS block."""
    _build_into(ED, repos.main)
    (repos.main / "nightshift").mkdir(exist_ok=True)
    (repos.main / "nightshift/explore_data.py").write_text("# stand-in\n")
    (repos.main / "nightshift/logs.py").write_text("# stand-in\n")
    repos.codeowners("/docs/prereg/ @E\n" + block)
    repos.push_main("exploration extract")
    repos.sync_dev()


# ============================================================ (1) allowlist only, rows after the cutoff never parsed
def test_q019_builder_reads_only_the_allowlist_and_never_parses_post_cutoff_rows(tmp_path, main_cfg, monkeypatch):
    ED = _ed()
    opened = []
    real_open, real_date, real_float = ED._open_source, ED._to_date, ED._to_float
    monkeypatch.setattr(ED, "_open_source", lambda p: (opened.append(Path(p).name), real_open(p))[1])

    def to_date(s):
        assert s <= "2019-12-31", f"parsed a post-cutoff date {s!r}"
        return real_date(s)

    def to_float(s):
        assert "BOOM" not in s and "NaN-not" not in s, f"converted a post-cutoff value {s!r}"
        return real_float(s)
    monkeypatch.setattr(ED, "_to_date", to_date)
    monkeypatch.setattr(ED, "_to_float", to_float)

    out = _build_into(ED, tmp_path)
    assert sorted(opened) == ["a.csv", "b.csv"]                         # never not_listed.csv
    ext = out["extract"]
    assert ext["data_end"] == "2019-12-31" and ext["last_date"] == "2019-12-31"
    assert sorted(s["id"] for s in ext["series"]) == ["a_level", "b_rate"]
    rows = list(csv.DictReader((tmp_path / EXTRACT).open()))
    assert max(r["date"] for r in rows) == "2019-12-31"
    assert {r["series"] for r in rows} == {"a_level", "b_rate"}          # extra_unlisted never extracted
    assert len([r for r in rows if r["series"] == "a_level"]) == 4
    assert len([r for r in rows if r["series"] == "b_rate"]) == 2
    assert ext["sha256"] == hashlib.sha256((tmp_path / EXTRACT).read_bytes()).hexdigest()
    for s in ext["series"]:
        assert s["source"] and s["licence"] and s["path"]               # every series carries its licence basis


def test_q019_builder_cutoff_is_mains_and_unreadable_refuses(tmp_path, main_cfg):
    ED = _ed()
    main_cfg["cfg"] = _cfg("2019-12-30")                                # main tighter than the dev copy (2021)
    out = _build_into(ED, tmp_path)
    assert out["extract"]["last_date"] == "2019-12-30"
    main_cfg["cfg"] = C.MainConfigError("git fetch origin main failed: fixture")
    with pytest.raises(ED.Refused, match="cutoff"):
        _build_into(ED, tmp_path / "x")
    assert not (tmp_path / "x" / EXTRACT).exists()


@pytest.mark.parametrize("change, why", [
    ({"path": "../outside.csv"}, "inside"),
    ({"path": "/etc/hostname"}, "inside"),
    ({"licence": ""}, "licence"),
    ({"source": ""}, "source"),
    ({"source": "Norgate futures export"}, "licensed"),
    ({"licence": "Databento settlement prices"}, "licensed"),
])
def test_q019_builder_refuses_sources_off_the_allowlist_rules(tmp_path, main_cfg, change, why):
    ED = _ed()
    m = _manifest()
    m["sources"][0].update(change)
    (tmp_path.parent / "outside.csv").write_text("date,level\n2019-01-01,1\n")
    with pytest.raises(ED.Refused, match=why):
        _build_into(ED, tmp_path, m)
    assert not (tmp_path / EXTRACT).exists()


def test_q019_builder_refuses_unsorted_or_non_iso_dates(tmp_path, main_cfg):
    ED = _ed()
    _write_sources(tmp_path)
    (tmp_path / "src/a.csv").write_text("date,level\n2019-12-30,1\n2019-12-27,2\n")
    mp = tmp_path / "m.json"
    mp.write_text(json.dumps(_manifest()))
    with pytest.raises(ED.Refused, match="ascending"):
        ED.build(mp, src_root=tmp_path, out_dir=tmp_path / "o")
    (tmp_path / "src/a.csv").write_text("date,level\n30/12/2019,1\n")
    with pytest.raises(ED.Refused, match="YYYY-MM-DD"):
        ED.build(mp, src_root=tmp_path, out_dir=tmp_path / "o")


# ===================================================== (2) forward-looking or revised-vintage columns are refused
@pytest.mark.parametrize("col", [
    {"column": "debt_change_next5y_pp", "series": "debt", "point_in_time": True},
    {"column": "gdp_fwd_1y", "series": "gdp", "point_in_time": True},
    {"column": "level", "series": "level_forward", "point_in_time": True},
    {"column": "cpi_latest_vintage", "series": "cpi", "point_in_time": True},
    {"column": "gdp_revised", "series": "gdp", "point_in_time": True},
    {"column": "level", "series": "a_level", "point_in_time": False},
    {"column": "level", "series": "a_level"},                               # not marked point-in-time
    {"column": "level", "series": "a_level", "point_in_time": "yes"},       # only literal true counts
])
def test_q019_builder_refuses_forward_looking_or_unmarked_columns(tmp_path, main_cfg, col):
    ED = _ed()
    m = _manifest()
    m["sources"][0]["columns"] = [col]
    with pytest.raises(ED.Refused):
        _build_into(ED, tmp_path, m)
    assert not (tmp_path / EXTRACT).exists()


# ============================================================= (3) the loader trusts only origin/main's manifest
def test_q019_loader_serves_mains_extract_up_to_the_cutoff(repos, main_cfg):
    ED = _ed()
    _ready_main(ED, repos)
    df = ED.load(repo=repos.dev)
    assert sorted(df.columns) == ["a_level", "b_rate"]
    assert str(df.index.max().date()) == "2019-12-31"
    assert df.loc["2019-12-31", "a_level"] == 2.5
    assert list(ED.load(["b_rate"], repo=repos.dev).columns) == ["b_rate"]
    with pytest.raises(ED.Refused, match="not in main's manifest"):
        ED.load(["not_a_series"], repo=repos.dev)


def test_q019_loader_works_without_data_in_the_checkout(repos, main_cfg):
    """The sparse-checkout design: the explorer's checkout has no data/ at all; the loader reads main's objects."""
    ED = _ed()
    _ready_main(ED, repos)
    for p in (repos.dev / "data/exploration").iterdir():
        p.unlink()
    assert str(ED.load(repo=repos.dev).index.max().date()) == "2019-12-31"


def test_q019_loader_refuses_an_extract_edited_on_dev_with_a_matching_dev_manifest(repos, main_cfg):
    ED = _ed()
    _ready_main(ED, repos)
    ext, man = repos.dev / EXTRACT, repos.dev / MANIFEST
    ext.write_text(ext.read_text() + "2020-01-02,a_level,9.9\n")       # a 2020 row smuggled in on dev
    m = json.loads(man.read_text())
    m["extract"]["sha256"] = hashlib.sha256(ext.read_bytes()).hexdigest()
    m["extract"]["data_end"] = m["extract"]["last_date"] = "2020-01-02"
    man.write_text(json.dumps(m, indent=1))
    _git(repos.dev, "commit", "-qam", "dev edit")
    with pytest.raises(ED.Refused, match="main"):
        ED.load(repo=repos.dev)


def test_q019_loader_refuses_a_manifest_that_exists_only_on_dev(repos, main_cfg):
    ED = _ed()
    _build_into(ED, repos.dev)
    _git(repos.dev, "add", "-A")
    _git(repos.dev, "commit", "-qm", "dev only")
    with pytest.raises(ED.Refused, match="main"):
        ED.load(repo=repos.dev)


@pytest.mark.parametrize("bad", [C.MainConfigError("git fetch origin main failed: fixture"),
                                 {"window": {"start": "22:30"}}])
def test_q019_loader_refuses_when_mains_cutoff_is_unreadable(repos, main_cfg, bad):
    ED = _ed()
    _ready_main(ED, repos)
    main_cfg["cfg"] = bad
    with pytest.raises(ED.Refused, match="cutoff"):
        ED.load(repo=repos.dev)


def test_q019_loader_refuses_an_extract_ending_after_mains_cutoff(repos, main_cfg):
    ED = _ed()
    _ready_main(ED, repos)
    main_cfg["cfg"] = _cfg("2019-12-30")                 # main's cutoff tightened after the build
    with pytest.raises(ED.Refused, match="after"):
        ED.load(repo=repos.dev)
    # an extract on main with a post-cutoff row, even with a self-consistent manifest claiming 2019-12-31
    main_cfg["cfg"] = _cfg("2019-12-31")
    ext, man = repos.main / EXTRACT, repos.main / MANIFEST
    ext.write_text(ext.read_text() + "2020-01-02,a_level,9.9\n")
    m = json.loads(man.read_text())
    m["extract"]["sha256"] = hashlib.sha256(ext.read_bytes()).hexdigest()
    man.write_text(json.dumps(m, indent=1))
    repos.push_main("bad extract")
    repos.sync_dev()
    with pytest.raises(ED.Refused, match="after"):
        ED.load(repo=repos.dev)


def test_q019_loader_refuses_a_hash_mismatch_on_main(repos, main_cfg):
    ED = _ed()
    _ready_main(ED, repos)
    ext = repos.main / EXTRACT
    ext.write_text(ext.read_text().replace("2.5", "2.6"))
    repos.push_main("extract edited without the manifest")
    repos.sync_dev()
    with pytest.raises(ED.Refused, match="sha256"):
        ED.load(repo=repos.dev)


def test_q019_loader_never_reads_the_dev_config():
    """AST: the loader module never calls C.load / config.load (the dev checkout's config)."""
    tree = ast.parse((ROOT / "nightshift/explore_data.py").read_text(encoding="utf-8"))
    bad = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "load"
           and isinstance(n.value, ast.Name) and n.value.id in ("C", "config")]
    assert bad == [], bad


# ========================================== (4) the guard keeps night-explorer off until main protects the loader
@pytest.fixture
def guard_env(monkeypatch, main_cfg, repos):
    """The guard CLI against the temporary repos: main's config patched, no Actions API, empty state and queue."""
    monkeypatch.setattr(C, "ROOT", repos.dev)
    monkeypatch.setattr(G, "busy_runs", lambda cfg, **k: [])
    monkeypatch.setattr(S, "load", lambda *a, **k: S.empty())
    monkeypatch.setattr(Q, "parse", lambda text: [])            # approved queue empty: explorer would be next
    return repos


def _guard(capsys, *argv) -> tuple[int, dict]:
    rc = G.main([*argv, "--now", NOW])
    return rc, json.loads(capsys.readouterr().out)


def test_q019_guard_keeps_explorer_off_until_main_has_the_manifest(guard_env, capsys):
    rc, v = _guard(capsys, "check", "night-explorer")
    assert rc == 4 and not v["go"], f"night-explorer allowed without main's manifest: {v}"
    assert any("explore" in r for r in v["reasons"]), v
    rc, v = _guard(capsys, "next")
    assert v["next"] != "night-explorer", f"guard next answered night-explorer without main's manifest: {v}"
    # night-worker is unaffected
    rc, v = _guard(capsys, "check", "night-worker")
    assert rc == 0 and v["go"], v


@pytest.mark.parametrize("block, missing", [
    ("/nightshift/explore_data.py @E\n/data/exploration/ @E\n", "nightshift/logs.py"),
    ("/data/exploration/ @E\n/nightshift/logs.py @E\n", "nightshift/explore_data.py"),
    ("/nightshift/explore_data.py @E\n/data/exploration/manifest.json @E\n/nightshift/logs.py @E\n", EXTRACT),
])
def test_q019_guard_keeps_explorer_off_until_codeowners_covers_everything(guard_env, capsys, block, missing):
    ED = _ed()
    _ready_main(ED, guard_env, block)
    rc, v = _guard(capsys, "check", "night-explorer")
    assert rc == 4 and any(missing in r for r in v["reasons"]), v
    rc, v = _guard(capsys, "next")
    assert v["next"] != "night-explorer", v


def test_q019_guard_codeowners_outside_the_block_does_not_count(guard_env, capsys):
    ED = _ed()
    _ready_main(ED, guard_env, "")
    p = guard_env.main / ".github/CODEOWNERS"
    p.write_text(p.read_text() + FULL_BLOCK)                    # after protected:end: not protected
    guard_env.push_main("lines outside the block")
    rc, v = _guard(capsys, "check", "night-explorer")
    assert rc == 4, v


def test_q019_guard_lets_explorer_run_once_main_is_ready(guard_env, capsys):
    ED = _ed()
    _ready_main(ED, guard_env)
    rc, v = _guard(capsys, "check", "night-explorer")
    assert rc == 0 and v["go"], v
    rc, v = _guard(capsys, "next")
    assert v["next"] == "night-explorer", v


def test_q019_guard_gate_fails_safe(guard_env, capsys, main_cfg, monkeypatch):
    ED = _ed()
    _ready_main(ED, guard_env)
    monkeypatch.setattr(ED, "explorer_gate", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    rc, v = _guard(capsys, "check", "night-explorer")
    assert rc == 4, v
    rc, v = _guard(capsys, "next")
    assert v["next"] != "night-explorer", v


def test_q019_pure_guard_functions_honour_the_gate():
    cfg, st = _cfg(), S.empty()
    now = datetime.fromisoformat(NOW)
    assert not G.check("night-explorer", now, cfg, st, [], explorer_gate=["no manifest"])["go"]
    assert G.check("night-worker", now, cfg, st, [], explorer_gate=["no manifest"])["go"]
    assert G.next_routine(now, cfg, st, [], 0, explorer_gate=["no manifest"])["next"] == "stop"


# ======================================================================= (5) no real extract built by the night
@pytest.fixture
def real_exploration_untouched():
    d = ROOT / "data/exploration"
    snap = lambda: sorted((p.name, p.stat().st_mtime_ns) for p in d.iterdir()) if d.exists() else None  # noqa: E731
    before = snap()
    yield
    assert snap() == before, "a test wrote to the real data/exploration"


def test_q019_build_cli_needs_authorisation_and_refuses_under_a_night_lock(tmp_path, main_cfg, monkeypatch,
                                                                           capsys, real_exploration_untouched):
    ED = _ed()
    _write_sources(tmp_path)
    (tmp_path / "m.json").write_text(json.dumps(_manifest()))
    args = ["build", "--manifest", str(tmp_path / "m.json"), "--src-root", str(tmp_path), "--out", str(tmp_path / "o")]
    with pytest.raises(SystemExit):
        ED.main(args)                                           # no --authorised-by
    st = S.empty()
    st["lock"] = {"routine": "night-worker", "acquired_at": "2026-11-09T15:00:00+00:00", "session": "s"}
    monkeypatch.setattr(S, "load", lambda *a, **k: st)
    assert ED.main(args + ["--authorised-by", "Ethan"]) == 3
    assert "night" in capsys.readouterr().out
    assert not (tmp_path / "o").exists()
    monkeypatch.setattr(S, "load", lambda *a, **k: S.empty())
    assert ED.main(args + ["--authorised-by", "Ethan"]) == 0
    assert json.loads((tmp_path / "o/manifest.json").read_text())["extract"]["authorised_by"] == "Ethan"

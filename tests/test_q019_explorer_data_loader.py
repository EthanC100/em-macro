"""Q019: exploration reads data only through one loader (nightshift/explore_data.py) that serves a frozen extract
truncated at MAIN's explorer.data_end. The extract lives in the private store (em-macro-data); only its manifest and
hashes are public (config/exploration_manifest.json), and the loader trusts only origin/main's copy of the manifest
(never the dev checkout). The guard keeps night-explorer off until main has that manifest, protects the loader, the
sandbox, the manifest and nightshift/logs.py in its CODEOWNERS block, and runs the explorer in the sandbox
(nightshift/explore_sandbox.py): a git-less allowlisted copy of dev with no data/ or results/ anywhere.

Synthetic fixtures only: C.load_main is monkeypatched (never the live config/night.yaml), git runs on temporary
repositories with a bare origin and a fixture store (never the real remotes or em-macro-data), the Actions API, state
and queue are stubbed, and every build writes under tmp_path. No real data file is read and no real extract is built.
Post-cutoff rows in the fixtures are poison (invalid UTF-8, NUL bytes, unterminated quotes, words where numbers
belong): decoding, tokenising or converting any of them fails the build, and the tokeniser and converters are also
wrapped to fail the test if they ever see a post-cutoff row."""
from __future__ import annotations

import ast
import base64
import csv
import hashlib
import importlib
import io
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from nightshift import config as C
from nightshift import guard as G
from nightshift import logs as LG
from nightshift import queue as Q
from nightshift import state as S

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures/night/night.yaml"
NOW = "2026-11-09T23:40:00+08:00"          # inside the chain window, no busy window
MANIFEST = "config/exploration_manifest.json"
STORE_PATH = "exploration/v1/extract.csv"
MUST_PROTECT = ("nightshift/explore_data.py", "nightshift/explore_sandbox.py", MANIFEST, "nightshift/logs.py")
FULL_BLOCK = ("/nightshift/explore_data.py @E\n/nightshift/explore_sandbox.py @E\n/config/exploration_manifest.json @E\n"
              "/nightshift/logs.py @E\n")
MARK = 'python -I "$MAINCODE/run.py" --repo "$PWD" create'


def _ed():
    """The loader module (absent before Q019: those tests fail on the import)."""
    return importlib.import_module("nightshift.explore_data")


def _sb():
    return importlib.import_module("nightshift.explore_sandbox")


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


@pytest.fixture(autouse=True)
def no_real_store(monkeypatch, tmp_path):
    """Never the real em-macro-data: no store unless a test sets one, no clone URL that resolves, no token."""
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path / "no-store"))
    monkeypatch.setenv("DATA_REPO_URL", str(tmp_path / "no-store.git"))
    monkeypatch.delenv("DATA_REPO_READ_TOKEN", raising=False)


# ------------------------------------------------------------------------------------------------ git fixtures
def _git(cwd: Path, *a: str) -> str:
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main", *a],
                       cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


class Repos:
    """A bare origin, a clone where 'main' commits are made (as Ethan would), a dev checkout (the routine's), and a
    fixture private store (a work tree whose objects the loader reads, plus a bare copy for the clone route)."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.origin, self.main, self.dev = tmp / "origin.git", tmp / "main_wt", tmp / "dev_wt"
        self.store, self.store_bare = tmp / "store", tmp / "store.git"
        _git(tmp, "init", "-q", "--bare", str(self.origin))
        _git(tmp, "clone", "-q", str(self.origin), str(self.main))
        _git(self.main, "checkout", "-q", "-b", "main")
        (self.main / "README").write_text("fixture\n")
        self.codeowners("/docs/prereg/ @E\n")
        self.push_main("base")
        _git(tmp, "clone", "-q", str(self.origin), str(self.dev))
        _git(self.dev, "checkout", "-q", "-b", "dev")
        _git(self.dev, "push", "-q", "origin", "dev")
        _git(tmp, "init", "-q", str(self.store))
        (self.store / "ledger").mkdir()
        (self.store / "ledger/futures_settlements.csv").write_text("date,contract,settle\n2026-11-02,ESZ6,SECRET\n")
        self.push_store("store base")

    def codeowners(self, block: str) -> None:
        p = self.main / ".github/CODEOWNERS"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# header\n# protected:start\n{block}# protected:end\n/other/ @E\n")

    def push_main(self, msg: str) -> None:
        _git(self.main, "add", "-A")
        _git(self.main, "commit", "-q", "--allow-empty", "-m", msg)
        _git(self.main, "push", "-q", "origin", "main")

    def sync_dev(self) -> None:
        _git(self.dev, "fetch", "-q", "origin")
        _git(self.dev, "merge", "-q", "--no-edit", "origin/main")
        _git(self.dev, "push", "-q", "origin", "dev")

    def push_dev(self, msg: str) -> None:
        _git(self.dev, "add", "-A")
        _git(self.dev, "commit", "-q", "-m", msg)
        _git(self.dev, "push", "-q", "origin", "dev")

    def push_store(self, msg: str) -> None:
        _git(self.store, "add", "-A")
        _git(self.store, "commit", "-q", "--allow-empty", "-m", msg)
        if self.store_bare.exists():
            shutil.rmtree(self.store_bare)
        _git(self.tmp, "clone", "-q", "--bare", str(self.store), str(self.store_bare))
        _git(self.store_bare, "config", "uploadpack.allowFilter", "true")
        _git(self.store_bare, "config", "uploadpack.allowAnySHA1InWant", "true")


@pytest.fixture
def repos(tmp_path, monkeypatch):
    r = Repos(tmp_path)
    monkeypatch.setenv("EM_MACRO_DATA", str(r.store))
    return r


# ------------------------------------------------------------------------------------------- synthetic sources
PRE = [("2019-12-26", "1.0", "5.0"), ("2019-12-27", "1.5", ""), ("2019-12-30", "2.0", "5.5"),
       ("2019-12-31", "2.5", "6.0")]
# After the cutoff: poison. Any decode, tokenise or float() of these lines raises or is caught by the wrapped helpers.
POISON = [b"2020-01-02,BOOM,BOOM", b"2020-01-03,\xff\xfe\x00not utf-8,\x00", b'2020-03-31,"unterminated,1',
          b"2021-06-30,NaN-not-a-number,x", b"garbage line with no date at all", b"zz,1,2"]


def _write_sources(root: Path) -> None:
    """Two public-looking synthetic files; rows after 2019-12-31 are poison. A third file in the same folder is NOT
    on the allowlist."""
    (root / "src").mkdir(parents=True, exist_ok=True)
    lines = [b"date,level,extra_unlisted"] + [f"{d},{a},{b}".encode() for d, a, b in PRE] + POISON
    (root / "src/a.csv").write_bytes(b"\n".join(lines) + b"\n")
    (root / "src/b.csv").write_bytes(b"obs_date,rate\n2019-11-29,3.25\n2019-12-31,3.5\n2020-01-31,BOOM\xff\n")
    (root / "src/not_listed.csv").write_text("date,secret\n2019-01-01,1\n2021-01-01,2\n")


def _col(column, series, **over):
    return {"column": column, "series": series, "source": f"Synthetic public statistic {series} (fixture)",
            "licence": "public domain (fixture)", "point_in_time": True, **over}


def _manifest(**over) -> dict:
    m = {"schema": 1, "note": "synthetic fixture", "store": {"repo": "fixture/store", "path": STORE_PATH},
         "sources": [
             {"id": "srcA", "path": "src/a.csv", "source": "fixture file A", "date_column": "date",
              "columns": [_col("level", "a_level")],
              "excluded": [{"column": "extra_unlisted", "reason": "fixture"}]},
             {"id": "srcB", "path": "src/b.csv", "source": "fixture file B", "date_column": "obs_date",
              "columns": [_col("rate", "b_rate")]}]}
    m.update(over)
    return m


def _build(ED, src: Path, store: Path, manifest: dict | None = None) -> dict:
    _write_sources(src)
    mp = src / "m.json"
    mp.write_text(json.dumps(manifest or _manifest(), indent=1))
    return ED.build(mp, src_root=src, store_root=store)


def _ready_main(ED, repos: Repos, block: str = FULL_BLOCK, routine: str = MARK, pin: bool = True) -> dict:
    """The extract built into the store and committed there; main gets the manifest, the real nightshift code (so a
    sandbox made from dev runs the real loader), a CODEOWNERS block and a night-explorer routine."""
    man = _build(ED, repos.tmp / "src_root", repos.store)
    repos.push_store("exploration extract")
    if pin:
        (repos.tmp / "pin.json").write_text(json.dumps(man))
        man = ED.pin(repos.tmp / "pin.json", repos.store)
    (repos.main / "config").mkdir(exist_ok=True)
    ED.write_manifest(man, repos.main / MANIFEST)
    nd = repos.main / "nightshift"
    nd.mkdir(exist_ok=True)
    for f in (ROOT / "nightshift").glob("*.py"):
        shutil.copy(f, nd / f.name)
    (repos.main / "CLAUDE.md").write_text("rules\n")
    (repos.main / "requirements.txt").write_text("pyyaml\n")
    rd = repos.main / ".claude/routines"
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "night-explorer.md").write_text(f"# routine\n```\n{routine} --dest /tmp/x\n```\n" if routine else "# r\n")
    repos.codeowners("/docs/prereg/ @E\n" + block)
    repos.push_main("exploration manifest")
    repos.sync_dev()
    return man


# ============================================================ (1) allowlist only, rows after the cutoff never parsed
def test_q019_builder_reads_only_the_allowlist_and_never_parses_post_cutoff_rows(tmp_path, main_cfg, monkeypatch):
    ED = _ed()
    opened = []
    real_open, real_date, real_float, real_split = ED._open_source, ED._to_date, ED._to_float, ED._split
    monkeypatch.setattr(ED, "_open_source", lambda p: (opened.append(Path(p).name), real_open(p))[1])

    def to_date(s):
        assert s <= "2019-12-31", f"parsed a post-cutoff date {s!r}"
        return real_date(s)

    def to_float(s):
        assert "BOOM" not in s and "NaN-not" not in s, f"converted a post-cutoff value {s!r}"
        return real_float(s)

    def split(text):
        assert not text.startswith(("2020", "2021", "garbage", "zz")), f"tokenised a post-cutoff line {text!r}"
        return real_split(text)
    monkeypatch.setattr(ED, "_to_date", to_date)
    monkeypatch.setattr(ED, "_to_float", to_float)
    monkeypatch.setattr(ED, "_split", split)

    store = tmp_path / "store"
    out = _build(ED, tmp_path, store)
    assert sorted(opened) == ["a.csv", "b.csv"]                         # never not_listed.csv
    ext = out["extract"]
    assert ext["data_end"] == "2019-12-31" and ext["last_date"] == "2019-12-31"
    assert ext["store_path"] == STORE_PATH and ext["store_commit"] is None
    assert sorted(s["id"] for s in ext["series"]) == ["a_level", "b_rate"]
    eb = (store / STORE_PATH).read_bytes()
    rows = list(csv.DictReader(io.StringIO(eb.decode())))
    assert max(r["date"] for r in rows) == "2019-12-31"
    assert {r["series"] for r in rows} == {"a_level", "b_rate"}          # extra_unlisted never extracted
    assert len([r for r in rows if r["series"] == "a_level"]) == 4
    assert len([r for r in rows if r["series"] == "b_rate"]) == 2
    assert ext["sha256"] == hashlib.sha256(eb).hexdigest() and ext["bytes"] == len(eb) and ext["rows"] == 6
    for s in ext["series"]:
        assert s["source"] and s["licence"]                             # every series carries its licence basis
    assert not (tmp_path / "config").exists() and not (tmp_path / "data").exists()   # nothing public written


def test_q019_poison_rows_would_fail_if_they_were_ever_decoded(tmp_path, main_cfg):
    """The fixture is real poison: moved before the cutoff, the same bytes make the build refuse."""
    ED = _ed()
    main_cfg["cfg"] = _cfg("2021-12-31")             # a looser main cutoff lets the builder reach the poison
    with pytest.raises(ED.Refused):
        _build(ED, tmp_path, tmp_path / "store")
    assert not (tmp_path / "store").exists()


def test_q019_builder_cutoff_is_mains_and_unreadable_refuses(tmp_path, main_cfg):
    ED = _ed()
    main_cfg["cfg"] = _cfg("2019-12-30")                                # main tighter than the dev copy (2021)
    out = _build(ED, tmp_path, tmp_path / "store")
    assert out["extract"]["last_date"] == "2019-12-30"
    main_cfg["cfg"] = C.MainConfigError("git fetch origin main failed: fixture")
    with pytest.raises(ED.Refused, match="cutoff"):
        _build(ED, tmp_path / "x", tmp_path / "x/store")
    assert not (tmp_path / "x/store").exists()


@pytest.mark.parametrize("change, why", [
    ({"path": "../outside.csv"}, "inside"),
    ({"path": "/etc/hostname"}, "inside"),
    ({"path": "src/missing.csv"}, "inside"),
    ({"source": "Norgate futures export"}, "licensed"),
    ({"path": "src/a.csv", "source": "copy of em-macro-data/ledger"}, "licensed"),
])
def test_q019_builder_refuses_sources_off_the_allowlist_rules(tmp_path, main_cfg, change, why):
    ED = _ed()
    m = _manifest()
    m["sources"][0].update(change)
    (tmp_path.parent / "outside.csv").write_text("date,level\n2019-01-01,1\n")
    with pytest.raises(ED.Refused, match=why):
        _build(ED, tmp_path, tmp_path / "store", m)
    assert not (tmp_path / "store").exists()


@pytest.mark.parametrize("over, why", [
    ({"licence": ""}, "licence"),
    ({"source": ""}, "source"),
    ({"licence": "Databento settlement prices"}, "licensed"),
])
def test_q019_builder_needs_each_columns_public_source_and_licence(tmp_path, main_cfg, over, why):
    ED = _ed()
    m = _manifest()
    m["sources"][0]["columns"] = [_col("level", "a_level", **over)]
    with pytest.raises(ED.Refused, match=why):
        _build(ED, tmp_path, tmp_path / "store", m)


def test_q019_builder_refuses_unsorted_non_iso_or_late_date_column(tmp_path, main_cfg):
    ED = _ed()
    _write_sources(tmp_path)
    mp = tmp_path / "m.json"
    mp.write_text(json.dumps(_manifest()))
    (tmp_path / "src/a.csv").write_text("date,level\n2019-12-30,1\n2019-12-27,2\n")
    with pytest.raises(ED.Refused, match="ascending"):
        ED.build(mp, src_root=tmp_path, store_root=tmp_path / "o")
    (tmp_path / "src/a.csv").write_text("date,level\n2019-12-30,1\n2019-12-30,2\n")
    with pytest.raises(ED.Refused, match="ascending"):
        ED.build(mp, src_root=tmp_path, store_root=tmp_path / "o")
    (tmp_path / "src/a.csv").write_text("date,level\n30/12/2019,1\n")
    with pytest.raises(ED.Refused, match="YYYY-MM-DD"):
        ED.build(mp, src_root=tmp_path, store_root=tmp_path / "o")
    (tmp_path / "src/a.csv").write_text("level,date\n1,2019-12-30\n")       # date not first: would need tokenising
    with pytest.raises(ED.Refused, match="first column"):
        ED.build(mp, src_root=tmp_path, store_root=tmp_path / "o")
    assert not (tmp_path / "o").exists()


@pytest.mark.parametrize("path", ["data/exploration/extract.csv", "exploration/../ledger/x.csv", "/exploration/x.csv",
                                  "exploration/v1/extract.json", ""])
def test_q019_builder_writes_only_under_the_stores_exploration_folder(tmp_path, main_cfg, path):
    ED = _ed()
    with pytest.raises(ED.Refused, match="store.path"):
        _build(ED, tmp_path, tmp_path / "store", _manifest(store={"path": path}))
    with pytest.raises(ED.Refused, match="store root"):
        ED.build(tmp_path / "m.json", src_root=tmp_path, store_root=None)


def test_q019_builder_records_provenance_and_refuses_a_modified_source(tmp_path, main_cfg):
    ED = _ed()
    src = tmp_path / "src_repo"
    src.mkdir()
    _git(src, "init", "-q")
    _write_sources(src)
    (src / "m.json").write_text(json.dumps(_manifest()))
    _git(src, "add", "-A")
    _git(src, "commit", "-qm", "sources")
    out = ED.build(src / "m.json", src_root=src, store_root=tmp_path / "store")
    prov = {p["id"]: p for p in out["extract"]["sources"]}
    assert prov["srcA"]["commit"] == _git(src, "rev-parse", "HEAD")
    assert prov["srcA"]["blob"] == _git(src, "rev-parse", "HEAD:src/a.csv")
    with (src / "src/a.csv").open("ab") as f:
        f.write(b"2022-01-03,1,1\n")
    with pytest.raises(ED.Refused, match="clean"):
        ED.build(src / "m.json", src_root=src, store_root=tmp_path / "store2")


# ===================================================== (2) forward-looking or revised-vintage columns are refused
@pytest.mark.parametrize("col", [
    _col("debt_change_next5y_pp", "debt"),
    _col("gdp_fwd_1y", "gdp"),
    _col("level", "level_forward"),
    _col("cpi_latest_vintage", "cpi"),
    _col("gdp_revised", "gdp"),
    _col("level", "a_level", point_in_time=False),
    {k: v for k, v in _col("level", "a_level").items() if k != "point_in_time"},    # not marked point-in-time
    _col("level", "a_level", point_in_time="yes"),                                  # only literal true counts
    _col("extra_unlisted", "x"),                                                    # listed and excluded
])
def test_q019_builder_refuses_forward_looking_or_unmarked_columns(tmp_path, main_cfg, col):
    ED = _ed()
    m = _manifest()
    m["sources"][0]["columns"] = [col]
    with pytest.raises(ED.Refused):
        _build(ED, tmp_path, tmp_path / "store", m)
    assert not (tmp_path / "store").exists()


def test_q019_real_manifest_is_a_valid_allowlist_built_within_mains_cutoff():
    """The public manifest committed with this change: every column public, licensed, point-in-time, nothing
    forward-looking, nothing licensed, built extract within 2019-12-31. Reads the manifest only, never data."""
    ED = _ed()
    man = json.loads((ROOT / MANIFEST).read_text(encoding="utf-8"))
    assert man["store"]["path"].startswith("exploration/")
    for s in man["sources"]:
        assert not s["path"].startswith(("results/", "data/ledger", "data/janus")), s["path"]
        excluded = {x["column"] for x in s.get("excluded", [])}
        for c in s["columns"]:
            assert c["point_in_time"] is True and c["source"] and c["licence"], c
            assert not ED.FORWARD.search(c["column"].lower()) and not ED.LICENSED.search(c["source"] + c["licence"])
            assert c["column"] not in excluded
    ext = ED.check_manifest(man, datetime(2019, 12, 31).date(), "this checkout")
    assert ext["data_end"] <= "2019-12-31" and ext["last_date"] <= "2019-12-31"
    assert ext["store_commit"] and ext["authorised_by"]
    assert {s["id"] for s in ext["series"]} == {c["series"] for s in man["sources"] for c in s["columns"]}


# ============================================================= (3) the loader trusts only origin/main's manifest
def test_q019_loader_serves_mains_extract_from_the_store_up_to_the_cutoff(repos, main_cfg):
    ED = _ed()
    _ready_main(ED, repos)
    df = ED.load(repo=repos.dev)
    assert sorted(df.columns) == ["a_level", "b_rate"]
    assert str(df.index.max().date()) == "2019-12-31"
    assert df.loc["2019-12-31", "a_level"] == 2.5
    assert list(ED.load(["b_rate"], repo=repos.dev).columns) == ["b_rate"]
    with pytest.raises(ED.Refused, match="not in main's manifest"):
        ED.load(["not_a_series"], repo=repos.dev)


def test_q019_public_repo_holds_the_manifest_and_hashes_only(repos, main_cfg):
    ED = _ed()
    _ready_main(ED, repos)
    files = _git(repos.main, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
    assert not [f for f in files if f.endswith(".csv")], files
    for f in files:
        assert b"a_level,2.5" not in (repos.main / f).read_bytes(), f       # no extract row is public
    assert len(json.loads((repos.main / MANIFEST).read_text())["extract"]["sha256"]) == 64


def test_q019_loader_reads_the_store_through_a_one_file_temporary_clone(repos, main_cfg, monkeypatch, tmp_path):
    """No store on disk: a blobless clone without checkout downloads only the extract's blob and is deleted, so the
    store's other files (settlements) never land on disk."""
    ED = _ed()
    _ready_main(ED, repos)
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path / "absent"))
    monkeypatch.setenv("DATA_REPO_URL", repos.store_bare.as_uri())
    made = []
    real = ED.tempfile.mkdtemp
    monkeypatch.setattr(ED.tempfile, "mkdtemp", lambda **k: (made.append(real(**k)), made[-1])[1])
    df = ED.load(repo=repos.dev)
    assert str(df.index.max().date()) == "2019-12-31"
    assert made and not any(Path(m).exists() for m in made)


def test_q019_store_errors_never_show_the_token(repos, main_cfg, monkeypatch, tmp_path):
    ED = _ed()
    _ready_main(ED, repos)
    tok = "github_pat_FIXTURE_SECRET_123"
    monkeypatch.setenv("DATA_REPO_READ_TOKEN", tok)
    monkeypatch.setenv("EM_MACRO_DATA", str(tmp_path / "absent"))
    monkeypatch.setenv("DATA_REPO_URL", str(tmp_path / "missing.git"))
    with pytest.raises(ED.Refused) as e:
        ED.load(repo=repos.dev)
    b64 = base64.b64encode(f"x-access-token:{tok}".encode()).decode()
    assert tok not in str(e.value) and b64 not in str(e.value)


def test_q019_loader_refuses_a_store_extract_that_is_not_mains(repos, main_cfg):
    """A different extract in the store (a 2020 row appended, or any edit) never matches main's sha256."""
    ED = _ed()
    _ready_main(ED, repos, pin=False)
    p = repos.store / STORE_PATH
    p.write_bytes(p.read_bytes() + b"2020-01-02,a_level,9.9\n")
    repos.push_store("store edited")
    with pytest.raises(ED.Refused, match="sha256"):
        ED.load(repo=repos.dev)


def test_q019_loader_refuses_a_manifest_edited_on_dev_to_match_a_new_extract(repos, main_cfg):
    ED = _ed()
    _ready_main(ED, repos, pin=False)
    p = repos.store / STORE_PATH
    p.write_bytes(p.read_bytes() + b"2020-01-02,a_level,9.9\n")
    repos.push_store("store edited")
    m = json.loads((repos.dev / MANIFEST).read_text())
    m["extract"]["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    m["extract"]["data_end"] = m["extract"]["last_date"] = "2020-01-02"
    (repos.dev / MANIFEST).write_text(json.dumps(m, indent=1))
    _git(repos.dev, "commit", "-qam", "dev edit")
    with pytest.raises(ED.Refused, match="main"):
        ED.load(repo=repos.dev)


def test_q019_loader_refuses_a_manifest_that_exists_only_on_dev(repos, main_cfg):
    ED = _ed()
    man = _build(ED, repos.tmp / "s", repos.store)
    (repos.dev / "config").mkdir(exist_ok=True)
    ED.write_manifest(man, repos.dev / MANIFEST)
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
    _ready_main(ED, repos, pin=False)
    main_cfg["cfg"] = _cfg("2019-12-30")                 # main's cutoff tightened after the build
    with pytest.raises(ED.Refused, match="after"):
        ED.load(repo=repos.dev)
    # an extract with a post-cutoff row and a self-consistent manifest on main claiming 2019-12-31
    main_cfg["cfg"] = _cfg("2019-12-31")
    p = repos.store / STORE_PATH
    p.write_bytes(p.read_bytes() + b"2020-01-02,a_level,9.9\n")
    repos.push_store("bad extract")
    m = json.loads((repos.main / MANIFEST).read_text())
    m["extract"]["sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    (repos.main / MANIFEST).write_text(json.dumps(m, indent=1))
    repos.push_main("bad manifest")
    repos.sync_dev()
    with pytest.raises(ED.Refused, match="after"):
        ED.load(repo=repos.dev)


def test_q019_loader_never_reads_the_dev_config():
    """AST: the loader and the sandbox never call C.load / config.load (the dev checkout's config)."""
    for f in ("explore_data.py", "explore_sandbox.py", "logs.py"):
        tree = ast.parse((ROOT / "nightshift" / f).read_text(encoding="utf-8"))
        bad = [n.lineno for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr == "load"
               and isinstance(n.value, ast.Name) and n.value.id in ("C", "config")]
        assert bad == [], (f, bad)


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
    assert any(MANIFEST in r for r in v["reasons"]), v
    rc, v = _guard(capsys, "next")
    assert v["next"] != "night-explorer", f"guard next answered night-explorer without main's manifest: {v}"
    rc, v = _guard(capsys, "check", "night-worker")              # night-worker is unaffected
    assert rc == 0 and v["go"], v


@pytest.mark.parametrize("block, missing", [
    (FULL_BLOCK.replace("/nightshift/logs.py @E\n", ""), "nightshift/logs.py"),
    (FULL_BLOCK.replace("/nightshift/explore_data.py @E\n", ""), "nightshift/explore_data.py"),
    (FULL_BLOCK.replace("/nightshift/explore_sandbox.py @E\n", ""), "nightshift/explore_sandbox.py"),
    (FULL_BLOCK.replace("/config/exploration_manifest.json @E\n", ""), MANIFEST),
])
def test_q019_guard_keeps_explorer_off_until_codeowners_covers_everything(guard_env, capsys, block, missing):
    ED = _ed()
    _ready_main(ED, guard_env, block)
    rc, v = _guard(capsys, "check", "night-explorer")
    assert rc == 4 and any(missing in r for r in v["reasons"]), v
    rc, v = _guard(capsys, "next")
    assert v["next"] != "night-explorer", v


def test_q019_guard_keeps_explorer_off_until_mains_routine_uses_the_sandbox(guard_env, capsys):
    ED = _ed()
    _ready_main(ED, guard_env, routine="")
    rc, v = _guard(capsys, "check", "night-explorer")
    assert rc == 4 and any("sandbox" in r for r in v["reasons"]), v
    (guard_env.dev / ".claude/routines/night-explorer.md").write_text(MARK + "\n")   # on dev only: does not count
    guard_env.push_dev("dev routine")
    rc, v = _guard(capsys, "check", "night-explorer")
    assert rc == 4, v


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


def test_q019_guard_gate_fails_safe(guard_env, capsys, monkeypatch):
    ED = _ed()
    _ready_main(ED, guard_env)
    monkeypatch.setattr(ED, "explorer_gate", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    rc, v = _guard(capsys, "check", "night-explorer")
    assert rc == 4, v
    rc, v = _guard(capsys, "next")
    assert v["next"] != "night-explorer", v


def test_q019_state_acquire_night_explorer_is_gated(guard_env, capsys, tmp_path):
    sp = tmp_path / "state.json"
    rc = S.main(["acquire", "night-explorer", "--state", str(sp)])
    assert rc == 3 and "gated" in capsys.readouterr().out
    assert not sp.exists()


def test_q019_pure_guard_functions_honour_the_gate_and_evaluate_it_when_not_given(monkeypatch):
    cfg, st = _cfg(), S.empty()
    now = datetime.fromisoformat(NOW)
    assert not G.check("night-explorer", now, cfg, st, [], explorer_gate=["no manifest"])["go"]
    assert G.check("night-worker", now, cfg, st, [], explorer_gate=["no manifest"])["go"]
    assert G.next_routine(now, cfg, st, [], 0, explorer_gate=["no manifest"])["next"] == "stop"
    calls = []
    monkeypatch.setattr(G, "gate_reasons", lambda: (calls.append(1), ["closed (fixture)"])[1])
    assert not G.check("night-explorer", now, cfg, S.empty(), [])["go"]          # omitted: evaluated, closed
    assert G.next_routine(now, cfg, S.empty(), [], 0)["next"] == "stop"
    assert len(calls) == 2
    assert G.check("night-worker", now, cfg, S.empty(), [])["go"] and len(calls) == 2   # never for the worker


# ============================================== (5) the sandbox: no data/, results/ or git; only the allowlist
PLANTED = {
    "data/processed/daily_panel.csv": "date,FX\n2020-03-02,LEAK2020\n",
    "results/systematic/paper_pnl.csv": "month,ret\n2021-01,LEAK2020\n",
    "tests/fixtures/live/data/processed/panel.csv": "2022-01-03,LEAK2020\n",
    "trials.csv": "trial_id,name,hypothesis,design_sample,test_sample,result,decision,notes\n"
                  "T01,carry,carry pays,2005-01..2019-12,2020-01..2026-09,Sharpe LEAK2020,kept,LEAK2020\n",
    "docs/prereg/T01.md": "T01 out of sample 2020-2026: Sharpe LEAK2020\n",
    "README.md": "Results 2020-2026: LEAK2020\n",
    "nightshift/data/cache.csv": "2020-01-02,LEAK2020\n",
    "lab/results/x.csv": "2020-01-02,LEAK2020\n",
    ".explore/sandbox.json": '{"cutoff": "2026-12-31"}',
    ".explore/extract.csv": "date,series,value\n2020-01-02,a_level,LEAK2020\n",
    "docs/prereg_drafts/README.md": "drafts\n",
    "lab/sleeves/README.md": "sleeves\n",
}


def _plant(repos: Repos) -> None:
    for rel, text in PLANTED.items():
        p = repos.dev / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    (repos.dev / "lab/link").symlink_to("../data/processed/daily_panel.csv")
    (repos.dev / "results/exploration").mkdir(parents=True, exist_ok=True)
    (repos.dev / "results/exploration/log.csv").write_text(",".join(LG.EXP_COLS) + "\n"
                                                           "2026-11-01,H0,V0,old,2005-01-03,2019-06-28,10,sharpe,0.1,,,,\n")
    repos.push_dev("dev with live files")
    _git(repos.main, "pull", "-q", "origin", "dev")
    _git(repos.main, "push", "-q", "origin", "main")          # trials.csv with results on main too


@pytest.fixture
def sandbox(guard_env, tmp_path):
    ED, SB = _ed(), _sb()
    _ready_main(ED, guard_env)
    _plant(guard_env)
    dest = tmp_path / "sbx" / "explore"
    out = SB.create(dest, repo=guard_env.dev)
    return dest, out


def test_q019_sandbox_has_no_data_results_git_or_live_files(sandbox):
    dest, out = sandbox
    SB = _sb()
    assert out["cutoff"] == "2019-12-31" and out["skipped"] == [], out    # lab/link, lab/results: never considered
    assert not (dest / ".git").exists()
    names = {p.relative_to(dest).as_posix() for p in dest.rglob("*")}
    assert not [n for n in names if set(Path(n).parts) & {"data", "results", "fixtures", ".git"}], names
    assert {"CLAUDE.md", "requirements.txt", "nightshift/explore_data.py", "lab/sleeves/README.md",
            "docs/prereg_drafts/README.md"} <= names
    assert not {"README.md", "trials.csv", "docs/prereg/T01.md"} & names
    for p in dest.rglob("*"):
        if p.is_file():
            assert b"LEAK2020" not in p.read_bytes(), p
    assert SB.audit(dest) == []
    trials = list(csv.DictReader((dest / ".explore/tested_trials.csv").open()))
    assert trials == [{"trial_id": "T01", "name": "carry"}]                 # hypothesis text can carry outcomes


def test_q019_sandbox_loader_works_with_no_git_and_no_network(sandbox, monkeypatch):
    dest, _ = sandbox
    ED = _ed()
    import socket

    def no(*a, **k):
        raise AssertionError("the sandbox loader touched git or the network")
    monkeypatch.setattr(subprocess, "run", no)
    monkeypatch.setattr(socket, "socket", no)
    monkeypatch.setattr(C, "load_main", no)
    df = ED.load(repo=dest)
    assert str(df.index.max().date()) == "2019-12-31" and sorted(df.columns) == ["a_level", "b_rate"]


def test_q019_sandbox_runs_the_real_code_standalone(sandbox):
    """End to end in a subprocess, cwd = the sandbox: the copied loader serves the bundle, logs.py writes the
    sandbox's provisional log and refuses 2020, and git finds no repository."""
    dest, _ = sandbox
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["PYTHONPATH"] = str(dest)
    env["GIT_CEILING_DIRECTORIES"] = str(dest.parent)

    def run(*a):
        return subprocess.run(list(a), cwd=dest, capture_output=True, text=True, env=env, timeout=120)
    r = run(sys.executable, "-c", "from nightshift import explore_data as E; d=E.load(); print(d.index.max().date())")
    assert r.returncode == 0 and r.stdout.strip() == "2019-12-31", r.stderr
    base = [sys.executable, "-m", "nightshift.logs", "variant", "--hypothesis", "H1", "--description", "d",
            "--data-start", "2005-01-03", "--metric", "sharpe", "--value", "0.3"]
    assert run(*base, "--variant", "V1", "--data-end", "2019-06-28").returncode == 0
    r = run(*base, "--variant", "V2", "--data-end", "2020-01-02")
    assert r.returncode == 1 and "2020" in r.stdout
    assert run(*base, "--variant", "V0", "--data-end", "2019-06-28").returncode == 1      # already in dev's log
    rows = list(csv.DictReader((dest / ".explore/out/variants.csv").open()))
    assert [x["variant_id"] for x in rows] == ["V1"]
    assert run("git", "show", "origin/main:data/processed/daily_panel.csv").returncode != 0


def test_q019_sandbox_tampering_is_refused_inside_and_at_collect(sandbox, guard_env, tmp_path, monkeypatch):
    dest, _ = sandbox
    ED, SB = _ed(), _sb()
    ext = dest / ".explore/extract.csv"
    good = ext.read_bytes()
    ext.write_bytes(good + b"2020-01-02,a_level,9.9\n")
    with pytest.raises(ED.Refused, match="sha256"):
        ED.load(repo=dest)
    ext.write_bytes(good)
    # the explorer loosens its sandbox's cutoff and logs a 2020 variant there; collect re-checks against main's
    meta = json.loads((dest / ".explore/sandbox.json").read_text())
    meta["cutoff"] = "2026-12-31"
    (dest / ".explore/sandbox.json").write_text(json.dumps(meta))
    monkeypatch.setattr(C, "ROOT", dest)
    LG.log_variant({"hypothesis_id": "H1", "variant_id": "V1", "description": "ok", "data_start": "2005-01-03",
                    "data_end": "2019-06-28", "metric": "m", "value": "1"})
    LG.log_variant({"hypothesis_id": "H1", "variant_id": "V2", "description": "2020", "data_start": "2005-01-03",
                    "data_end": "2020-06-30", "metric": "m", "value": "1"})
    assert str(ED.load(repo=dest).index.max().date()) == "2019-12-31"   # a looser cutoff serves nothing new
    monkeypatch.setattr(C, "ROOT", guard_env.dev)
    (dest / "lab/sleeves/L001.yaml").write_text("id: L001\n")
    (dest / "docs/prereg_drafts/H1.md").write_text("# H1\n")
    (dest / ".explore/out/exploration/H1").mkdir(parents=True)
    (dest / ".explore/out/exploration/H1/table.csv").write_text("variant,sharpe\nV1,0.3\n")
    (dest / "nightshift/evil.py").write_text("print('not collected')\n")
    real_log = tmp_path / "real_log.csv"
    r = SB.collect(dest, repo=guard_env.dev, log_path=real_log)
    assert r["variants_logged"] == ["V1"]
    assert len(r["refused"]) == 1 and r["refused"][0].startswith("V2") and "2020" in r["refused"][0]
    assert sorted(r["copied"]) == ["docs/prereg_drafts/H1.md", "lab/sleeves/L001.yaml",
                                   "results/exploration/H1/table.csv"]
    assert not (guard_env.dev / "nightshift/evil.py").exists()
    assert [x["variant_id"] for x in csv.DictReader(real_log.open())] == ["V1"]


def test_q019_sandbox_is_refused_while_the_gate_is_closed_or_inside_a_repo(guard_env, tmp_path):
    ED, SB = _ed(), _sb()
    with pytest.raises(SB.Refused, match="gate closed"):
        SB.create(tmp_path / "sbx1", repo=guard_env.dev)
    assert not (tmp_path / "sbx1").exists()
    _ready_main(ED, guard_env)
    with pytest.raises(SB.Refused, match="outside the checkout"):
        SB.create(guard_env.dev / "sbx", repo=guard_env.dev)
    with pytest.raises(SB.Refused, match="work tree"):
        SB.create(guard_env.main / "sbx", repo=guard_env.dev)


def test_q019_sandbox_refuses_a_dev_log_reaching_past_the_cutoff(guard_env, tmp_path):
    ED, SB = _ed(), _sb()
    _ready_main(ED, guard_env)
    (guard_env.dev / "results/exploration").mkdir(parents=True)
    (guard_env.dev / "results/exploration/log.csv").write_text(",".join(LG.EXP_COLS) + "\n"
                                                               "2026-11-01,H0,V0,x,2005-01-03,2020-06-30,1,m,1,,,,\n")
    guard_env.push_dev("hand-edited log")
    with pytest.raises(SB.Refused, match="after main's cutoff"):
        SB.create(tmp_path / "sbx", repo=guard_env.dev)
    assert not (tmp_path / "sbx").exists()


# ======================================================================= (6) no real extract built by the night
def test_q019_build_cli_needs_authorisation_a_store_and_refuses_under_a_night_lock(tmp_path, main_cfg, monkeypatch,
                                                                                   capsys):
    ED = _ed()
    _write_sources(tmp_path)
    (tmp_path / "m.json").write_text(json.dumps(_manifest()))
    args = ["build", "--manifest", str(tmp_path / "m.json"), "--src-root", str(tmp_path)]
    with pytest.raises(SystemExit):
        ED.main(args + ["--store-root", str(tmp_path / "o")])            # no --authorised-by
    with pytest.raises(SystemExit):
        ED.main(args + ["--authorised-by", "Ethan"])                      # no store
    st = S.empty()
    st["lock"] = {"routine": "night-worker", "acquired_at": "2026-11-09T15:00:00+00:00", "session": "s"}
    monkeypatch.setattr(S, "load", lambda *a, **k: st)
    args += ["--store-root", str(tmp_path / "o"), "--authorised-by", "Ethan"]
    assert ED.main(args) == 3
    assert "night" in capsys.readouterr().out
    assert not (tmp_path / "o").exists()
    monkeypatch.setattr(S, "load", lambda *a, **k: S.empty())
    assert ED.main(args) == 0
    assert json.loads((tmp_path / "m.json").read_text())["extract"]["authorised_by"] == "Ethan"
    assert (tmp_path / "o" / STORE_PATH).exists()


def test_q019_new_files_are_protected():
    from nightshift import protected as P
    pats = P.patterns()
    for rel in MUST_PROTECT:
        assert P.protected([rel], pats) == [rel], rel
        assert any(P.matches(q, rel) for q in P.block_patterns((ROOT / ".github/CODEOWNERS").read_text())), rel
        assert any(P.matches(q, rel) for q in P.ALWAYS), rel


def test_q019_sandbox_code_comes_from_main_not_dev(guard_env, tmp_path):
    """A dev copy of the loader (or of logs.py) never enters the sandbox: code and rules are main's."""
    ED, SB = _ed(), _sb()
    _ready_main(ED, guard_env)
    (guard_env.dev / "nightshift/explore_data.py").write_text("SERVE_EVERYTHING = True\n")
    (guard_env.dev / "nightshift/extra_dev_module.py").write_text("x = 1\n")
    (guard_env.dev / "lab/sleeves").mkdir(parents=True, exist_ok=True)
    (guard_env.dev / "lab/sleeves/L009.yaml").write_text("id: L009\n")
    guard_env.push_dev("dev edits")
    dest = tmp_path / "sbx"
    SB.create(dest, repo=guard_env.dev)
    assert (dest / "nightshift/explore_data.py").read_bytes() == (ROOT / "nightshift/explore_data.py").read_bytes()
    assert not (dest / "nightshift/extra_dev_module.py").exists()
    assert (dest / "lab/sleeves/L009.yaml").exists()                    # the night's own outputs come from dev


def test_q019_collect_never_follows_links_out_of_the_sandbox(sandbox, guard_env, tmp_path):
    """A write folder replaced by a link into the private store would copy settlements into the public repo."""
    dest, _ = sandbox
    SB = _sb()
    shutil.rmtree(dest / "lab/sleeves")
    (dest / "lab/sleeves").symlink_to(guard_env.store / "ledger")
    (dest / ".explore/out/exploration/H1").mkdir(parents=True)
    (dest / ".explore/out/exploration/H1/fx.csv").symlink_to(guard_env.store / "ledger/futures_settlements.csv")
    r = SB.collect(dest, repo=guard_env.dev, log_path=tmp_path / "log.csv")
    assert r["copied"] == [], r
    assert any("lab/sleeves" in x for x in r["refused"]) and any("fx.csv" in x for x in r["refused"]), r
    assert not (guard_env.dev / "lab/sleeves/futures_settlements.csv").exists()


@pytest.mark.parametrize("name, body, why", [
    ("rows.csv", "date,fx\n2019-12-31,1.0\n2020-01-02,1.1\n", "dated after the cutoff"),
    ("monthly.csv", "month,ret\n2019-12,0.1\n2020-03,-0.2\n", "dated after the cutoff"),
    ("big.csv", "x\n" + "1\n" * 1_100_000, "over"),
    ("bin.csv", b"\xff\xfe\x00", "UTF-8"),
])
def test_q019_collect_refuses_late_dated_oversized_or_binary_tables(sandbox, guard_env, tmp_path, name, body, why):
    dest, _ = sandbox
    SB = _sb()
    d = dest / ".explore/out/exploration/H1"
    d.mkdir(parents=True)
    (d / name).write_bytes(body if isinstance(body, bytes) else body.encode())
    (d / "ok.csv").write_text("variant,sharpe,data_end\nV1,0.3,2019-06-28\n")
    r = SB.collect(dest, repo=guard_env.dev, log_path=tmp_path / "log.csv")
    assert r["copied"] == ["results/exploration/H1/ok.csv"], r
    assert len(r["refused"]) == 1 and why in r["refused"][0], r


def test_q019_collect_cli_writes_into_the_named_checkout(sandbox, guard_env, capsys):
    dest, _ = sandbox
    SB = _sb()
    (dest / "docs/prereg_drafts/H2.md").write_text("# H2\n")
    assert SB.main(["collect", "--sandbox", str(dest), "--into", str(guard_env.dev)]) == 0
    assert (guard_env.dev / "docs/prereg_drafts/H2.md").read_text() == "# H2\n"
    assert json.loads(capsys.readouterr().out)["copied"] == ["docs/prereg_drafts/H2.md"]


# ================================================== (7) The Opposition's attacks (review of 2026-11-12), now refused
def _main_code(repos: Repos, dest: Path) -> Path:
    """main's nightshift/ extracted outside every checkout (git archive), as the drafted routine runs it."""
    dest.mkdir(parents=True)
    arc = subprocess.run(["git", "archive", "origin/main", "nightshift"], cwd=repos.dev, capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(dest)], input=arc.stdout, check=True)
    return dest


RUN_PY = ("import pathlib, sys; sys.path.insert(0, str(pathlib.Path(__file__).parent))\n"
          "from nightshift.explore_sandbox import main; sys.exit(main(sys.argv[1:]))\n")   # docs/exploration_data.md s5


def _run_main_code(code: Path, *argv: str) -> subprocess.CompletedProcess:
    (code / "run.py").write_text(RUN_PY)
    return subprocess.run([sys.executable, "-I", str(code / "run.py"), *argv], capture_output=True, text=True,
                          timeout=300)


def test_q019_routine_draft_runs_the_tested_runner():
    """The runner in the drafted routine is the one the F1 test runs."""
    doc = (ROOT / "docs/exploration_data.md").read_text(encoding="utf-8")
    for line in RUN_PY.splitlines():
        assert line in doc, line
    assert _ed().SANDBOX_MARK in doc                     # applying the draft is what opens gate check 4
    assert 'python -I "$MAINCODE/run.py" --repo "$PWD" create --dest "$SBX"' in doc
    assert 'python -I "$MAINCODE/run.py" --repo "$PWD" collect --sandbox "$SBX" --into "$PWD"' in doc


def test_q019_F1_main_code_ignores_a_dev_config_that_loosens_the_cutoff(repos, tmp_path):
    """F1: dev's unprotected config.py wraps load_main to 2026. collect run from dev's code accepts a 2024 variant
    (the attack is real); main's code, extracted with git archive and run with python -I, refuses it."""
    ED = _ed()
    import nightshift.explore_data as EDm
    cfg_main = _cfg()
    real = C.load_main
    C.load_main = lambda *a, **k: cfg_main
    try:
        _ready_main(EDm, repos)
    finally:
        C.load_main = real
    (repos.main / "config/night.yaml").write_text(yaml.safe_dump(cfg_main))
    repos.push_main("main config")
    repos.sync_dev()
    with (repos.dev / "nightshift/config.py").open("a") as f:
        f.write("\n_real_load_main = load_main\n\n\ndef load_main(*a, **k):\n    c = _real_load_main(*a, **k)\n"
                "    c['explorer']['data_end'] = '2026-12-31'\n    return c\n")
    repos.push_dev("dev loosens the cutoff")
    code = _main_code(repos, tmp_path / "maincode")
    sbx = tmp_path / "sbx"
    r = _run_main_code(code, "--repo", str(repos.dev), "create", "--dest", str(sbx))
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads((sbx / ".explore/sandbox.json").read_text())["cutoff"] == "2019-12-31"
    assert b"_real_load_main" not in (sbx / "nightshift/config.py").read_bytes()      # the sandbox runs main's code
    head = ",".join(LG.EXP_COLS) + "\n"
    (sbx / ".explore/out/variants.csv").write_text(head + "2026-11-12,H1,V1,ok,2005-01-03,2019-06-28,1,m,1,,,,\n"
                                                   "2026-11-12,H1,V2,late,2005-01-03,2024-06-28,1,m,1,,,,\n")
    r = _run_main_code(code, "--repo", str(repos.dev), "collect", "--sandbox", str(sbx), "--into", str(repos.dev))
    out = json.loads(r.stdout)
    assert r.returncode == 1 and out["variants_logged"] == ["V1"] and out["refused"][0].startswith("V2"), out
    dev = subprocess.run([sys.executable, "-m", "nightshift.explore_sandbox", "collect", "--sandbox", str(sbx)],
                         cwd=repos.dev, capture_output=True, text=True, timeout=300)
    assert json.loads(dev.stdout)["variants_logged"] == ["V2"], dev.stdout + dev.stderr   # dev's code: the attack works


def test_q019_F2_dev_cannot_plant_data_or_results_in_the_allowlisted_folders(guard_env, tmp_path):
    ED, SB = _ed(), _sb()
    _ready_main(ED, guard_env)
    plant = {"lab/sleeves/p.csv": "date,fx\n2020-03-02,1\n",
             "lab/sleeves/L010.yaml": "id: L010\nlaunched: 2026-11-20\nretire_on: 2027-05-20\nnote: 2020-03-02 BRL -5%\n",
             "lab/sleeves/L011.yaml": "id: L011\nlaunched: 2026-11-20\nretire_on: 2027-05-20\n",
             "docs/prereg_drafts/x.md": "T18 2020-03-02: Sharpe 0.9\n",
             "docs/prereg_drafts/ok.md": "Test window 2020-01..2026-09, never run by the night shift.\n",
             "docs/prereg_drafts/sub/y.md": "nested\n",
             "lab/registry.csv": "id,launched\nL999,2020-01-02\n",
             "lab/notes.py": "LEAK = '2021-01-04'\n"}
    for rel, text in plant.items():
        (guard_env.dev / rel).parent.mkdir(parents=True, exist_ok=True)
        (guard_env.dev / rel).write_text(text)
    guard_env.push_dev("planted")
    dest = tmp_path / "sbx"
    out = SB.create(dest, repo=guard_env.dev)
    have = {p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()}
    assert {"lab/sleeves/L011.yaml", "docs/prereg_drafts/ok.md"} <= have
    assert not {"lab/sleeves/p.csv", "lab/sleeves/L010.yaml", "docs/prereg_drafts/x.md", "docs/prereg_drafts/sub/y.md",
                "lab/registry.csv", "lab/notes.py"} & have
    assert len(out["skipped"]) == 4, out["skipped"]


def test_q019_F3_collect_never_overwrites_the_log_or_publishes_a_secret(sandbox, guard_env, tmp_path, monkeypatch):
    dest, _ = sandbox
    SB = _sb()
    monkeypatch.setenv("NIGHT_EXPLORER_FIRE_TOKEN", "fixture-secret-value-123")
    (dest / ".explore/out/exploration/log.csv").write_text("logged_on,variant_id\n")
    (dest / "docs/prereg_drafts/env.md").write_text("NIGHT_EXPLORER_FIRE_TOKEN=fixture-secret-value-123\n")
    r = SB.collect(dest, repo=guard_env.dev, log_path=tmp_path / "log.csv")
    assert r["copied"] == [], r
    assert any("hypothesis folder" in x for x in r["refused"]) and any("NIGHT_EXPLORER_FIRE_TOKEN" in x
                                                                       for x in r["refused"]), r
    assert not any("fixture-secret-value-123" in x for x in r["refused"])


def test_q019_F4_no_store_access_and_no_build_from_inside_the_sandbox(sandbox, monkeypatch):
    dest, _ = sandbox
    ED = _ed()
    monkeypatch.setattr(C, "ROOT", dest)
    man = json.loads((dest / ".explore/manifest.json").read_text())
    with pytest.raises(ED.Refused, match="sandbox"):
        ED.store_extract(man["extract"])
    assert ED._blob_from_temp_clone(None, "ledger/futures_settlements.csv", []) is None
    with pytest.raises(ED.Refused, match="sandbox"):
        ED.build(dest / ".explore/manifest.json", src_root=dest, store_root=dest / "x")


def test_q019_F4_clone_routes_drop_git_tracing(monkeypatch):
    ED = _ed()
    monkeypatch.setenv("GIT_TRACE_CURL", "/tmp/trace.log")
    monkeypatch.setenv("GIT_TRACE", "1")
    monkeypatch.setenv("DATA_REPO_READ_TOKEN", "tok-fixture-123")
    routes, secrets = ED._clone_routes()
    for _, env in routes:
        assert "GIT_TRACE_CURL" not in env and "GIT_TRACE" not in env and "DATA_REPO_READ_TOKEN" not in env


def test_q019_F6_sandbox_log_copy_has_no_free_text_notes(guard_env, tmp_path):
    ED, SB = _ed(), _sb()
    _ready_main(ED, guard_env)
    (guard_env.dev / "results/exploration").mkdir(parents=True)
    (guard_env.dev / "results/exploration/log.csv").write_text(
        ",".join(LG.EXP_COLS) + "\n"
        "2026-11-01,H0,V0,carry on 2020-05-01 data,2005-01-03,2019-06-28,1,m,1,{\"p\": 1},x@y,,2020-26 Sharpe 0.9\n")
    guard_env.push_dev("log with notes")
    dest = tmp_path / "sbx"
    SB.create(dest, repo=guard_env.dev)
    rows = list(csv.DictReader((dest / ".explore/exploration_log.csv").open()))
    assert set(rows[0]) == set(SB.LOG_COLS) and rows[0]["description"].startswith("[withheld")
    assert "Sharpe" not in (dest / ".explore/exploration_log.csv").read_text()

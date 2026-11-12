"""Shared test helpers.

Ledger tests never read the live ledger (data/ledger/decisions.csv, forecasts.csv, seals.jsonl, marks, ...): those
files grow every time a decision or forecast is logged, which broke ledger-daily on 2026-11-06 when D003 was logged
(issue #23). ``seed_ledger`` builds a ledger from the frozen seed in tests/fixtures/ledger/ (D001, D002, F001-F005
and a few T-bill marks, as they stood on 2026-11-06) plus only the static configuration of the real one (the
instrument registry and the capacity reference), so the next ids are always D003 and F006.
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "tests/fixtures/ledger"
CONFIG_FILES = ("instruments.csv", "capacity_reference.csv")    # static configuration, not ledger contents


def seed_ledger(root: Path, marks: bool = True) -> Path:
    """Create ``root``/data/ledger from the frozen seed; returns ``root``."""
    led = root / "data/ledger"
    led.mkdir(parents=True, exist_ok=True)
    for f in CONFIG_FILES:
        shutil.copy(ROOT / "data/ledger" / f, led / f)
    for f in ("decisions.csv", "forecasts.csv") + (("marks.csv",) if marks else ()):
        shutil.copy(SEED / f, led / f)
    return root


# ----------------------------------------------------------------------------- frozen copies of the writers' files (Q025)
# Scheduled jobs rewrite results/systematic*/ (systematic-monthly), data/ledger/ and data/janus/ (ledger-daily, Janus,
# the clerk), results/shadows/, results/screener/, results/live_compare/, data/elections/ and the country panel. A
# test that reads those live files breaks when a job rewrites them, and systematic-monthly runs the whole suite
# before it commits: on 3 Dec 2026 tests/test_books.py would have failed on the new positions and the December
# rebalance would not have been committed (queue item Q025). Tests read the frozen copies in tests/fixtures/live/
# instead (taken from main 2075d1c on 2026-11-12; *.gz files are stored compressed), through ``frozen_repo``: a
# mirror of the repository whose entries are symlinks to the real ones, except the frozen files, with every Path
# constant (and default argument) of the loaded ledger/em_macro modules that points into the repository moved to
# the mirror. The mirror has no .git, so dates read from git history are None, never today's.
LIVE = ROOT / "tests/fixtures/live"


def frozen_copy(rel: str) -> Path:
    """The frozen copy of a writer-owned file (path relative to the repository root)."""
    p = LIVE / rel
    if not p.exists():
        raise FileNotFoundError(f"{rel} has no frozen copy in tests/fixtures/live")
    return p


# Directories frozen whole (the mirror holds exactly the copies), directories frozen in part (the mirror links only the
# listed live entries, "*" = every live entry that has no frozen copy), and writer directories with no frozen copy
# yet, left out of the mirror (they appear only after the 3 Dec 2026 rebalance or the shadows' go-live).
WHOLE = ("data/ledger", "data/janus", "data/elections", "results/shadows", "results/screener", "results/live_compare")
PARTIAL = {"results/systematic": ("fit", "test", "overlay"), "results/systematic_v1.1": ("freeze",),
           "data/processed": ("*",), "docs": ("*",)}     # docs: queue.md and agent-state.json (the night shift's)
ABSENT = ("data/commodities", "results/systematic/d005")


def _copy_frozen(src: Path, dest: Path) -> None:
    import gzip
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.name.endswith(".gz"):
        dest.with_name(src.name[:-3]).write_bytes(gzip.decompress(src.read_bytes()))
    else:
        shutil.copy(src, dest)


def make_frozen_repo(dest: Path) -> Path:
    """Build the mirror at ``dest`` and return it: everything is a symlink to the live repository (code,
    configuration, frozen results) except the WHOLE and PARTIAL directories' frozen copies; ABSENT is left out."""
    special = set(WHOLE) | set(PARTIAL) | set(ABSENT)
    ancestors = {Path(s).parents[i].as_posix() for s in special for i in range(len(Path(s).parts) - 1)}

    def walk(rel: str):
        out = dest / rel if rel else dest
        out.mkdir(parents=True, exist_ok=True)
        for e in sorted((ROOT / rel if rel else ROOT).iterdir()):
            r = f"{rel}/{e.name}" if rel else e.name
            if e.name == ".git" or r in special:
                continue
            if r in ancestors:
                walk(r)
            else:
                (dest / r).symlink_to(e, target_is_directory=e.is_dir())

    walk("")
    for d in WHOLE + tuple(PARTIAL):
        (dest / d).mkdir(parents=True, exist_ok=True)
        if (LIVE / d).is_dir():
            for f in (LIVE / d).rglob("*"):
                if f.is_file():
                    _copy_frozen(f, dest / d / f.relative_to(LIVE / d))
    for d, keep in PARTIAL.items():
        if not (ROOT / d).is_dir():
            continue
        for e in (ROOT / d).iterdir():
            if ("*" in keep or e.name in keep) and not (dest / d / e.name).exists() \
                    and f"{d}/{e.name}" not in special and not (LIVE / d / (e.name + ".gz")).exists():
                (dest / d / e.name).symlink_to(e, target_is_directory=e.is_dir())
    return dest


def _rebase(value, new_root: Path):
    try:
        return new_root / Path(value).relative_to(ROOT) if isinstance(value, Path) else value
    except ValueError:
        return value


def point_modules_at(new_root: Path, mp) -> None:
    """Move every Path constant and Path default argument of the loaded ledger.*/em_macro.*/nightshift.* modules that points into
    the repository to the same place under ``new_root`` (with pytest's MonkeyPatch ``mp``, so it is undone)."""
    import sys
    import types
    for name, mod in list(sys.modules.items()):
        if not (name in ("ledger", "nightshift") or name.startswith(("ledger.", "em_macro.", "nightshift."))) \
                or mod is None:
            continue
        for attr, val in list(vars(mod).items()):
            if isinstance(val, Path) and _rebase(val, new_root) is not val:
                mp.setattr(mod, attr, _rebase(val, new_root))
            elif isinstance(val, types.FunctionType) and val.__module__ == name:
                if val.__defaults__:
                    new = tuple(_rebase(v, new_root) for v in val.__defaults__)
                    if any(a is not b for a, b in zip(new, val.__defaults__)):
                        mp.setattr(val, "__defaults__", new)
                if val.__kwdefaults__:
                    kw = {k: _rebase(v, new_root) for k, v in val.__kwdefaults__.items()}
                    if any(kw[k] is not v for k, v in val.__kwdefaults__.items()):
                        mp.setattr(val, "__kwdefaults__", kw)


import contextlib  # noqa: E402

import pytest  # noqa: E402


@contextlib.contextmanager
def frozen_modules(root: Path):
    """While active, the ledger/em_macro/nightshift modules read the mirror ``root``."""
    from ledger import audit, books, build, changes, janus, marks, stress  # noqa: F401  (load before rebasing)
    with pytest.MonkeyPatch.context() as mp:
        point_modules_at(root, mp)         # the mirror's parent has no em-macro-data: no private store unless a
        yield root                         # test sets EM_MACRO_DATA itself


@pytest.fixture(scope="session")
def frozen_root(tmp_path_factory):
    """The mirror of the repository with the writers' files frozen (built once per test session)."""
    return make_frozen_repo(tmp_path_factory.mktemp("frozen_repo") / "em-macro")


@pytest.fixture
def frozen_repo(frozen_root):
    """For one test: the ledger/em_macro/nightshift modules read the frozen mirror; yields its root."""
    with frozen_modules(frozen_root) as root:
        yield root

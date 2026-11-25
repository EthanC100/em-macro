"""The First Light data-access cap (manhattan/firstlight/cap.py): nothing dated or published after 2019-12-31 is
loaded or read, whatever the configuration, the caller or the input types. Synthetic data only."""
from __future__ import annotations

import ast
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from manhattan import access, roles
from manhattan.engine import pit
from manhattan.firstlight import cap

ROOT = Path(__file__).resolve().parents[1]
DOM = "commodity_futures_daily"
SERIES = "synthetic_close"


def _days(a: date, b: date) -> list[date]:
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


def _capped(end: date = date(2019, 12, 31)) -> cap.CappedStore:
    c = cap.CappedStore(synthetic=True)
    d = _days(date(2019, 10, 1), end)
    c.add(SERIES, d, np.arange(len(d), dtype=float), lag_days=0)
    return c


# ---------------------------------------------------------------- the boundary

def test_the_cap_is_rule_4s_boundary_and_a_constant_in_code():
    assert cap.DATA_END == date(2019, 12, 31)
    src = (ROOT / "manhattan/firstlight/cap.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imported = {a.name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "config" not in imported and "yaml" not in imported and "manhattan.config" not in modules
    assert "manhattan.yaml" not in src.replace("config/manhattan.yaml``", "")   # mentioned in prose only


def test_the_last_capped_day_is_readable_inclusive():
    w = _capped().reader(caller="explorer", domain=DOM).window(date(2019, 12, 2), date(2019, 12, 31))
    assert w.role == roles.EXPLORATION
    p, _ = w.as_of(SERIES, date(2019, 12, 31))
    assert p[-1] == np.datetime64("2019-12-31")


@pytest.mark.parametrize("start,end", [
    (date(2019, 12, 2), date(2020, 1, 1)),        # one day over
    (date(2020, 1, 1), date(2020, 1, 1)),
    (date(2020, 1, 2), date(2020, 1, 31)),
    (date(2019, 1, 2), date(2021, 6, 1)),
    (date(2020, 1, 2), date(2026, 9, 30)),        # the protected confirmatory window
])
@pytest.mark.parametrize("caller", ["explorer", "session", roles.RUNNER])
def test_reads_after_the_cap_fail_closed_for_every_caller(start, end, caller):
    r = _capped().reader(caller=caller, domain=DOM)
    with pytest.raises(cap.CapError):
        r.window(start, end)


def test_no_value_after_the_window_end_can_leave_even_when_asked_for_a_later_day():
    w = _capped().reader(caller="explorer", domain=DOM).window(date(2019, 12, 2), date(2019, 12, 20))
    p, _ = w.as_of(SERIES, date(2020, 6, 30))       # pit caps t at the window's end
    assert p[-1] == np.datetime64("2019-12-20")


# ---------------------------------------------------------------- independence from configuration and callers

def test_the_cap_does_not_follow_a_widened_configuration(monkeypatch):
    """The audit's B.8 gap: exploration.data_end '2025-12-31' validates and makes 2021 an exploration date under the
    general fence. First Light's fence and reader ignore it."""
    from manhattan import config as mconfig
    widened = roles.Fence(exploration_end=date(2025, 12, 31), reserve={}, enabled=False)
    general = pit.Reader(_capped().store, caller="explorer", domain=DOM, fence=widened)
    assert roles.check_read("explorer", DOM, date(2021, 1, 4), date(2021, 1, 29), widened) == roles.EXPLORATION
    assert general.window(date(2021, 1, 4), date(2021, 1, 29)).role == roles.EXPLORATION   # the gap the cap closes
    monkeypatch.setattr(mconfig, "load", lambda *a, **k: {"exploration": {"data_end": "2025-12-31"}})
    assert cap.fence().exploration_end == cap.DATA_END and cap.fence().enabled is False and cap.fence().reserve == {}
    with pytest.raises(cap.CapError):
        _capped().reader(caller="explorer", domain=DOM).window(date(2021, 1, 4), date(2021, 1, 29))


def test_a_runner_cannot_turn_later_dates_into_forward_reads():
    """C9: with the general Reader a runner and a caller-supplied freeze read 2020+ dates as forward. First Light's
    reader takes no freeze date and no token."""
    assert roles.role_of(date(2020, 6, 1), DOM, cap.fence(), freeze=date(2019, 12, 31)) == roles.FORWARD
    r = _capped().reader(caller=roles.RUNNER, domain=DOM)
    with pytest.raises(cap.CapError):
        r.window(date(2020, 1, 2), date(2020, 1, 31))
    with pytest.raises(TypeError):
        cap.CappedReader(_capped(), caller=roles.RUNNER, domain=DOM, freeze=date(2019, 12, 31))
    with pytest.raises(TypeError):
        _capped().reader(caller=roles.RUNNER, domain=DOM, token=object())


def test_no_data_callers_are_still_refused_inside_the_cap():
    with pytest.raises(roles.RoleError):
        _capped().reader(caller="critic", domain=DOM).window(date(2019, 12, 2), date(2019, 12, 31))


# ---------------------------------------------------------------- ingestion

def test_values_dated_after_the_cap_are_refused_and_nothing_is_added():
    c = cap.CappedStore(synthetic=True)
    with pytest.raises(cap.CapError, match="dated"):
        c.add(SERIES, [date(2019, 12, 31), date(2020, 1, 2)], [1.0, 2.0], lag_days=0)
    assert c.store.names() == []


@pytest.mark.parametrize("kw", [
    {"available": [date(2020, 1, 3)]},             # describes 2019-12-31, published 2020-01-03
    {"lag_days": 1},                               # 2019-12-31 + 1 day
])
def test_values_published_after_the_cap_are_refused(kw):
    c = cap.CappedStore(synthetic=True)
    with pytest.raises(cap.CapError, match="published"):
        c.add(SERIES, [date(2019, 12, 31)], [1.0], **kw)
    assert c.store.names() == []


def test_values_published_on_the_cap_day_are_accepted():
    c = cap.CappedStore(synthetic=True)
    c.add(SERIES, [date(2019, 12, 27)], [1.0], available=[date(2019, 12, 31)])
    assert c.store.names() == [SERIES]


def test_a_direct_addition_to_the_store_is_detected_at_the_next_read_and_load():
    c = _capped()
    c.store.add(SERIES, [date(2020, 1, 2)], [9.0], lag_days=0)             # bypasses the cap
    with pytest.raises(cap.CapError, match="outside"):
        c.reader(caller="explorer", domain=DOM).window(date(2019, 12, 2), date(2019, 12, 31))
    with pytest.raises(cap.CapError, match="outside"):
        c.add("other", [date(2019, 12, 2)], [1.0], lag_days=0)


# ---------------------------------------------------------------- types

@pytest.mark.parametrize("start,end", [
    (datetime(2019, 12, 2), datetime(2019, 12, 31, 23, 59)),
    ("2019-12-02", "2019-12-31"),
    (np.datetime64("2019-12-02"), np.datetime64("2019-12-31")),
    (20191202, 20191231),
])
def test_only_calendar_days_are_accepted_for_reads(start, end):
    with pytest.raises(cap.CapError):
        _capped().reader(caller="explorer", domain=DOM).window(start, end)


@pytest.mark.parametrize("periods", [
    [datetime(2019, 12, 31, 23, 0)],
    ["2019-12-31"],
    np.array(["2019-12-31T23:00"], dtype="datetime64[m]"),
    np.array(["NaT"], dtype="datetime64[D]"),
    date(2019, 12, 31),
])
def test_only_calendar_days_are_accepted_for_loads(periods):
    with pytest.raises(cap.CapError):
        cap.CappedStore(synthetic=True).add(SERIES, periods, [1.0], lag_days=0)


@pytest.mark.parametrize("unit", ["2D", "3D", "7D"])
@pytest.mark.parametrize("which", ["periods", "available"])
def test_multi_day_units_are_refused_because_they_quantize_dates_across_the_cap(unit, which):
    """Review of PR #107: datetime64[3D] holding 2020-01-02 is the 2019-12-31 bucket; it must not load."""
    late = np.array(["2020-01-02"], dtype=f"datetime64[{unit}]")
    ok = np.array(["2019-12-02"], dtype="datetime64[D]")
    c = cap.CappedStore(synthetic=True)
    with pytest.raises(cap.CapError):
        if which == "periods":
            c.add(SERIES, late, [42.0], lag_days=0)
        else:
            c.add(SERIES, ok, [42.0], available=late)
    assert c.store.names() == []


@pytest.mark.parametrize("lag", [-1, 1.5, True, None])
def test_bad_publication_lags_are_refused(lag):
    kw = {"lag_days": lag} if lag is not None else {}
    with pytest.raises(cap.CapError):
        cap.CappedStore(synthetic=True).add(SERIES, [date(2019, 12, 2)], [1.0], **kw)


# ---------------------------------------------------------------- declared windows (the bound path, after D-10)

def _dw(end: date, role: str = roles.EXPLORATION, start: date = date(2015, 1, 2)) -> access.DeclaredWindow:
    return access.DeclaredWindow("w1", DOM, start, end, role, "evaluation", "0" * 64)


def test_declared_windows_inside_the_cap_pass():
    cap.check_declared_windows([_dw(date(2019, 12, 31))])


@pytest.mark.parametrize("w", [
    _dw(date(2020, 1, 1)),
    _dw(date(2026, 9, 30), start=date(2020, 1, 2)),
    _dw(date(2019, 12, 31), role=roles.RESERVE),
    _dw(date(2019, 12, 31), role=roles.FORWARD),
])
def test_declared_windows_past_the_cap_or_outside_exploration_are_refused(w):
    with pytest.raises(cap.CapError):
        cap.check_declared_windows([_dw(date(2019, 6, 28)), w])


def test_an_attempt_declares_at_least_one_window():
    with pytest.raises(cap.CapError):
        cap.check_declared_windows([])


# ---------------------------------------------------------------- dormancy

def test_nothing_in_manhattan_imports_first_light():
    for p in sorted((ROOT / "manhattan").rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith("manhattan/firstlight/"):
            continue
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom) and n.module and "firstlight" in n.module:
                pytest.fail(f"{rel} imports {n.module}")
            if isinstance(n, ast.Import) and any("firstlight" in a.name for a in n.names):
                pytest.fail(f"{rel} imports First Light")
            if isinstance(n, ast.ImportFrom) and n.module == "manhattan" and any(a.name == "firstlight"
                                                                                  for a in n.names):
                pytest.fail(f"{rel} imports First Light")


@pytest.mark.parametrize('where', ['periods', 'available'])
@pytest.mark.parametrize('subclass', ['masked', 'plain'])
def test_ingestion_refuses_date_array_subclasses_before_mutation(where, subclass):
    class Dates(np.ndarray):
        def max(self, *args, **kwargs):
            return np.datetime64('2019-12-31', 'D')
    days = np.array(['2019-12-30', '2020-06-01'], dtype='datetime64[D]')
    hostile = np.ma.array(days, mask=[False, True]) if subclass == 'masked' else days.view(Dates)
    ordinary = np.array(['2019-12-30', '2019-12-31'], dtype='datetime64[D]')
    c = cap.CappedStore(synthetic=True)
    before = c.store.data_hash()
    with pytest.raises(cap.CapError):
        c.add(SERIES, hostile if where == 'periods' else ordinary, [1., 2.],
              **({'lag_days': 0} if where == 'periods' else {'available': hostile}))
    assert c.store.data_hash() == before



def test_lag_ingestion_passes_the_checked_plain_availability_array(monkeypatch):
    c = cap.CappedStore(synthetic=True)
    seen = {}
    def add(series, periods, values, **kwargs):
        seen.update(kwargs)
        assert type(periods) is np.ndarray
        assert type(kwargs['available']) is np.ndarray
    monkeypatch.setattr(c.store, 'add', add)
    c.add(SERIES, [date(2019, 12, 30)], [1.], lag_days=1)
    assert seen['available'].tolist() == [date(2019, 12, 31)]

"""``roles.Fence.from_config`` fails closed on a reserve section it cannot read exactly as written.

A reserve window is found by its domain name (``fence.reserve.get(domain)``). An entry whose key YAML parsed as a
number, boolean, null or date was kept under a key no domain matches, so its reserve dates were silently
unprotected; ``enabled: "false"`` (a string) switched the reserve on; a window whose start is after its end
protected none of its dates. Each is now refused (``FenceConfigError``), every configuration that was valid parses
to the same fence as before, and ``manhattan.config.validate`` reports the same keys.

Every case is parsed from YAML text with ``yaml.safe_load``, as ``config.load`` does.
"""
from __future__ import annotations

import textwrap
from datetime import date, datetime

import pytest
import yaml

from manhattan import access, config as MC, roles

BASE = """
exploration:
  data_end: "2019-12-31"
reserve:
  enabled: {enabled}
  windows: {windows}
"""


def cfg(windows: str = "{}", enabled: str = "false", extra: str = "") -> dict:
    return yaml.safe_load(textwrap.dedent(BASE).format(enabled=enabled, windows=windows) + extra)


def _old_from_config(c: dict) -> roles.Fence:
    """``from_config`` as it was on main before this change, for comparison."""
    res = c.get("reserve", {})
    windows = {d: (roles._day(w["start"]), roles._day(w["end"])) for d, w in (res.get("windows") or {}).items()}
    return roles.Fence(exploration_end=roles._day(c["exploration"]["data_end"]), reserve=windows,
                       enabled=bool(res.get("enabled")))


# ----------------------------------------------------------------------------------------------- valid configurations

VALID = [
    ("{}", "false"),
    ("{fx_daily: {start: 2020-01-01, end: 2026-09-30}}", "false"),
    ("{fx_daily: {start: 2020-01-01, end: 2026-09-30}}", "true"),
    ('{"fx_daily": {start: "2020-01-01", end: "2026-09-30"}}', "true"),                       # quoted dates
    ("{fx_daily: {start: 2020-01-01, end: 2026-09-30}, equities_us: {start: 2021-01-04, end: 2026-06-30}}", "true"),
    ('{"1": {start: 2020-01-01, end: 2026-09-30}}', "true"),                                # a quoted numeric name
    ('{"yes": {start: 2020-01-01, end: 2026-09-30}}', "false"),
    ("{fx_daily: {start: 2020-01-01, end: 2020-01-01}}", "false"),                          # a one-day window
    ("{fx_daily: {start: 2020-01-01, end: 2026-09-30, note: ignored}}", "false"),            # extra keys, as before
    ("null", "false"),
]


@pytest.mark.parametrize("windows,enabled", VALID)
def test_valid_configurations_parse_to_the_same_fence_as_before(windows, enabled):
    c = cfg(windows, enabled)
    assert roles.Fence.from_config(c) == _old_from_config(c)
    assert all(type(k) is str for k in roles.Fence.from_config(c).reserve)


def test_the_repository_configuration_still_parses_and_validates():
    c = MC.load()
    assert roles.Fence.from_config(c) == _old_from_config(c)
    assert MC.validate(c) == []


def test_a_missing_reserve_section_is_no_reserve():
    c = yaml.safe_load('exploration:\n  data_end: "2019-12-31"\n')
    assert roles.Fence.from_config(c) == roles.Fence(date(2019, 12, 31), {}, False)


# ------------------------------------------------------------------------------------------------------ malformed keys

MALFORMED_KEYS = [
    ("{1: {start: 2020-01-01, end: 2026-09-30}}", 1),
    ("{1.5: {start: 2020-01-01, end: 2026-09-30}}", 1.5),
    ("{yes: {start: 2020-01-01, end: 2026-09-30}}", True),                 # YAML 1.1: yes/no/on/off are booleans
    ("{on: {start: 2020-01-01, end: 2026-09-30}}", True),
    ("{false: {start: 2020-01-01, end: 2026-09-30}}", False),
    ("{null: {start: 2020-01-01, end: 2026-09-30}}", None),
    ("{~: {start: 2020-01-01, end: 2026-09-30}}", None),
    ("{2020-01-01: {start: 2020-01-01, end: 2026-09-30}}", date(2020, 1, 1)),
    ('{"": {start: 2020-01-01, end: 2026-09-30}}', ""),
    ('{" fx_daily": {start: 2020-01-01, end: 2026-09-30}}', " fx_daily"),  # would not match the domain fx_daily
    ('{"fx_daily ": {start: 2020-01-01, end: 2026-09-30}}', "fx_daily "),
    ("{0x1F: {start: 2020-01-01, end: 2026-09-30}}", 31),
]


@pytest.mark.parametrize("windows,key", MALFORMED_KEYS)
def test_a_reserve_key_that_is_not_a_domain_name_is_refused(windows, key):
    c = cfg(windows, "true")
    assert key in c["reserve"]["windows"]                                   # what YAML made of it
    with pytest.raises(roles.FenceConfigError, match="not a domain name"):
        roles.Fence.from_config(c)
    assert any("not a domain name" in e for e in MC.validate(c))


@pytest.mark.parametrize("windows,key", MALFORMED_KEYS[:4])
def test_before_this_change_the_reserve_was_silently_unprotected(windows, key):
    """The defect, demonstrated: the old parse kept the entry under a key no domain name equals, so a read of the
    reserve dates on the domain the owner meant was allowed as exploration."""
    c = cfg(windows, "true", 'extra: 0\n')
    c["exploration"]["data_end"] = "2026-12-31"
    old = _old_from_config(c)
    name = str(key).lower() if isinstance(key, bool) else str(key)
    assert roles.check_read("session", name, date(2022, 1, 3), date(2022, 2, 1), old) == roles.EXPLORATION


# ----------------------------------------------------------------------------------------------- mixed-key configurations

@pytest.mark.parametrize("windows", [
    "{fx_daily: {start: 2020-01-01, end: 2026-09-30}, 1: {start: 2020-01-01, end: 2026-09-30}}",
    "{1: {start: 2020-01-01, end: 2026-09-30}, fx_daily: {start: 2020-01-01, end: 2026-09-30}}",
    '{fx_daily: {start: 2020-01-01, end: 2026-09-30}, "1": {start: 2020-01-01, end: 2026-09-30}, 2: {start: 2021-01-01, end: 2021-12-31}}',
    "{fx_daily: {start: 2020-01-01, end: 2026-09-30}, null: {start: 2020-01-01, end: 2026-09-30}}",
])
def test_one_malformed_key_refuses_the_whole_fence(windows):
    """Fail closed: the valid entries are not kept while the malformed one is dropped; nothing parses."""
    with pytest.raises(roles.FenceConfigError):
        roles.Fence.from_config(cfg(windows, "true"))


# -------------------------------------------------------------------------------------- security-sensitive edge cases

@pytest.mark.parametrize("enabled", ['"false"', '"true"', '"no"', "1", "0", "0.0", "[]", '""'])
def test_enabled_must_be_a_boolean_never_coerced(enabled):
    """``bool("false")`` is True: a quoted value used to switch the reserve on."""
    c = cfg("{fx_daily: {start: 2020-01-01, end: 2026-09-30}}", enabled)
    with pytest.raises(roles.FenceConfigError, match="enabled"):
        roles.Fence.from_config(c)


def test_a_quoted_false_used_to_enable_the_reserve():
    c = cfg("{fx_daily: {start: 2020-01-01, end: 2026-09-30}}", '"false"')
    assert _old_from_config(c).enabled is True


@pytest.mark.parametrize("window,why", [
    ("{start: 2026-09-30, end: 2020-01-01}", "starts after it ends"),
    ("{start: 2020-01-01}", "start and end"),
    ("{end: 2026-09-30}", "start and end"),
    ("[2020-01-01, 2026-09-30]", "start and end"),
    ('"2020-01-01..2026-09-30"', "start and end"),
    ("{start: 2020-01-01T00:00:00, end: 2026-09-30}", "date"),           # a datetime is not a date
    ("{start: 20200101, end: 2026-09-30}", "date"),
    ('{start: "2020-1-1", end: 2026-09-30}', "date"),
    ('{start: "2020-01-01 ", end: 2026-09-30}', "date"),
    ("{start: null, end: 2026-09-30}", "date"),
])
def test_a_malformed_window_is_refused(window, why):
    with pytest.raises(roles.FenceConfigError, match=why):
        roles.Fence.from_config(cfg("{fx_daily: " + window + "}", "true"))


def test_a_reversed_window_used_to_leave_its_dates_unprotected():
    c = cfg("{fx_daily: {start: 2026-09-30, end: 2020-01-01}}", "true")
    c["exploration"]["data_end"] = "2026-12-31"
    assert roles.check_read("session", "fx_daily", date(2022, 1, 3), date(2022, 2, 1), _old_from_config(c)) == \
        roles.EXPLORATION
    with pytest.raises(roles.FenceConfigError):
        roles.Fence.from_config(c)


@pytest.mark.parametrize("text,why", [
    ("exploration:\n  data_end: \"2019-12-31\"\nreserve: [1, 2]\n", "reserve must be a mapping"),
    ("exploration:\n  data_end: \"2019-12-31\"\nreserve:\n  windows: [fx_daily]\n", "map each domain"),
    ("reserve:\n  enabled: false\n", "data_end"),
    ("exploration:\n  data_end: 2019-12-31T00:00:00\n", "date"),
    ("- not a mapping\n", "mapping"),
])
def test_other_malformed_sections_are_refused(text, why):
    with pytest.raises(roles.FenceConfigError, match=why):
        roles.Fence.from_config(yaml.safe_load(text))


def test_the_verified_fence_path_fails_closed(monkeypatch):
    """``access`` reads the authoritative configuration through ``from_config``: a malformed reserve key is an
    ``AccessError`` there, so no attempt can be registered under it."""
    raw = textwrap.dedent(BASE).format(enabled="true", windows="{1: {start: 2020-01-01, end: 2026-09-30}}").encode()
    with pytest.raises(access.AccessError):
        access._fence_of(raw)


def test_a_valid_fence_still_protects_its_reserve():
    f = roles.Fence.from_config(cfg("{fx_daily: {start: 2020-01-01, end: 2026-09-30}}", "true"))
    with pytest.raises(roles.RoleError):
        roles.check_read("session", "fx_daily", date(2022, 1, 3), date(2022, 2, 1), f)
    assert f.reserve == {"fx_daily": (date(2020, 1, 1), date(2026, 9, 30))} and type(f.reserve["fx_daily"][0]) is date


def test_a_datetime_object_is_not_accepted_as_a_date():
    c = cfg("{fx_daily: {start: 2020-01-01, end: 2026-09-30}}", "true")
    c["reserve"]["windows"]["fx_daily"]["start"] = datetime(2020, 1, 1)
    with pytest.raises(roles.FenceConfigError):
        roles.Fence.from_config(c)

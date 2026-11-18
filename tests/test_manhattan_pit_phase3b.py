"""Data-only adversarial fixtures; these do not authenticate any real source."""
from copy import deepcopy
from datetime import date

import numpy as np
import pytest

from manhattan import ledger, spec
from manhattan.availability import AvailabilityError, sources_from_spec
from manhattan.engine import pit, evaluate
from manhattan.ops import compiler, data
from test_manhattan_pit_integrity import Archive, csv
import manhattan_attempt_fixtures as F


def source(frequency="monthly", kind="release_dates", label="period_start"):
    return {"name": "fabricated", "frequency": frequency, "period_label": label,
            "availability": {"kind": kind, "reference": "synthetic release manifest",
                             "day_mapping": "fixture midnight means usable at that day close"}}


def window(store):
    # Phase 4B: windows are opened by a Reader (or a registered attempt), never constructed directly
    return pit.Reader(store, caller="session", domain="test", fence=F.OPEN_FENCE).window(date(2010, 1, 1),
                                                                                       date(2011, 1, 1))


@pytest.mark.parametrize("unit", ["Y", "M", "W", "generic"])
@pytest.mark.parametrize("container", ["array", "object", "mixed"])
@pytest.mark.parametrize("field", ["period", "available", "cutoff"])
def test_ambiguous_numpy_precision(unit, container, field):
    value = np.datetime64("NaT") if unit == "generic" else np.datetime64("2010-01-01", unit)
    dates = np.array([value], dtype=object if container == "object" else value.dtype)
    if container == "mixed":
        dates = [value, np.datetime64("2010-01-02", "D")]
    store = pit.PitStore()
    with pytest.raises(pit.PitError):
        if field == "period":
            store.add("x", dates, np.ones(len(dates)), lag_days=0)
        elif field == "available":
            store.add("x", ["2009-01-01"] * len(dates), np.ones(len(dates)), available=dates)
        else:
            store.add("x", ["2010-01-01"], [1], lag_days=0)
            window(store).as_of("x", value if container != "object" else np.array(value, dtype=object))


def test_empty_generic_datetime_array_rejected():
    with pytest.raises(pit.PitError):
        pit.PitStore().add("x", np.array([], dtype="datetime64"), [], lag_days=0)


@pytest.mark.parametrize("unit", ["D", "h", "m", "s", "ms", "us", "ns"])
def test_day_and_finer_midnight_are_valid(unit):
    day = np.datetime64("2010-01-01", unit)
    store = pit.PitStore()
    store.add("x", [day], [1], available=[day])
    assert window(store).as_of("x", day)[1].tolist() == [1]


@pytest.mark.parametrize("frequency,periods,releases", [
    ("monthly", ["2010-01-01", "2010-02-01", "2010-01-01"], ["2010-02-18", "2010-03-26", "2010-04-09"]),
    ("quarterly", ["2010-01-01", "2010-04-01", "2010-01-01"], ["2010-04-29", "2010-08-06", "2010-09-03"]),
])
@pytest.mark.parametrize("kind", ["release_dates", "release_calendar"])
def test_irregular_release_and_revision_days(frequency, periods, releases, kind):
    src = source(frequency, kind)
    assert sources_from_spec({"data_sources": [src]}) == {src["name"]: src}
    st = pit.PitStore()
    st.add_source(src, periods, [10, 20, 11], available=releases)
    w = window(st)
    for cutoff, expected in [(str(np.datetime64(releases[0]) - np.timedelta64(1, "D")), []),
                             (releases[0], [10]), (releases[1], [10, 20]), (releases[2], [11, 20])]:
        assert w.as_of("fabricated", cutoff)[1].tolist() == expected
    assert w.as_of("fabricated", releases[0])[1].tolist() == [10]
    with pytest.raises(pit.PitError, match="per-vintage"):
        pit.lags_from_spec({"data_sources": [src]})


@pytest.mark.parametrize("label", ["period_start", "period_end", "publication_date"])
def test_period_label_never_substitutes_for_release(label):
    st = pit.PitStore()
    with pytest.raises(pit.PitError, match="per-vintage"):
        st.add_source(source(label=label), ["2010-01-01"], [1])


@pytest.mark.parametrize("field", ["frequency", "period_label", "availability"])
def test_missing_source_semantics_fail_compiler_and_lag_reader(field):
    src = source()
    del src[field]
    h = {"data_sources": [src]}
    assert compiler.check_hypothesis(h)
    with pytest.raises(pit.PitError):
        pit.lags_from_spec(h)
    with pytest.raises(pit.PitError):
        pit.PitStore().add_source(src, ["2010-01-01"], [1], available=["2010-02-15"])


@pytest.mark.parametrize("frequency", ["monthly", "quarterly", "irregular"])
def test_fixed_lag_on_non_daily_periods_is_rejected(frequency):
    src = source(frequency, "daily_lag")
    src["publication_lag_days"] = 45
    with pytest.raises(AvailabilityError):
        sources_from_spec({"data_sources": [src]})


def test_conflicting_and_ambiguous_declarations_fail():
    src = source()
    other = deepcopy(src)
    other["availability"]["reference"] = "different calendar"
    for sources in ([src, other], [{**src, "publication_lag_days": 30}]):
        with pytest.raises(AvailabilityError):
            sources_from_spec({"data_sources": sources})


def test_conservative_availability_needs_documentation_and_stays_reconstructed():
    src = source(kind="conservative")
    for field, value in (("assumption", "fixture only: use explicitly supplied delayed dates"),
                         ("release_history_unavailable", "fixture has no provider history"),
                         ("owner_approval", "fabricated approval record, not real authorization")):
        with pytest.raises(AvailabilityError):
            sources_from_spec({"data_sources": [src]})
        src["availability"][field] = value
    st = pit.PitStore()
    st.add_source(src, ["2010-01-01"], [1], available=["2010-03-31"])
    assert window(st).as_of("fabricated", "2010-03-30")[1].size == 0
    with pytest.raises(pit.PitError, match="reconstructed"):
        st.require_historical_evidence()


def test_legacy_records_remain_hashable_but_cannot_compile_or_supply_lags():
    legacy = {"data_sources": [{"name": "unknown", "publication_lag_days": 45}]}
    before = spec.canonical_bytes(legacy)
    assert any("frequency" in e for e in compiler.check_hypothesis(legacy))
    with pytest.raises(pit.PitError):
        pit.lags_from_spec(legacy)
    assert spec.canonical_bytes(legacy) == before


def test_backfill_taint_survives_capture_conversion_and_later_append(tmp_path, monkeypatch):
    archive = Archive(tmp_path)
    archive.capture(csv(("2010-01-01", 9), ("2010-01-04", 10)), "2010-01-04T21:00:00Z")
    st = data.first_seen(archive, ("synthetic",)).pit_store()
    st.add("x", ["2010-01-05"], [11], lag_days=0)
    assert window(st).as_of("x", "2010-01-05")[1].tolist() == [9, 10, 11]
    # Phase 4B: a reserve window exists only for a registered attempt (synthetic reserve fence and token)
    book = ledger.Ledger(tmp_path / "ledger.jsonl", writer="fixture", protocol="0" * 64)
    wid = "test:reserve"
    ctx = F.register(book, st, domain="test", start=date(2010, 1, 4), end=date(2010, 1, 5), role="reserve",
                     window_id=wid, designated=True,
                     fence=F.reserve_fence("test", date(2010, 1, 4), date(2010, 3, 31), date(2009, 12, 31)),
                     token=F.reserve_token("test", wid))
    reserve = ctx.window(st)
    def must_not_run(*args, **kwargs):
        pytest.fail("reconstructed reserve inputs reached the evaluator")
    monkeypatch.setattr(evaluate.backtest, "run", must_not_run)
    with pytest.raises(pit.PitError, match="reconstructed"):
        evaluate.evaluate(reserve, None, ledger=book, **F.spec_kwargs(designated=True), attempt=ctx)
    assert book.records()[-1]["type"] == "attempt_failed"                       # closed, never completed


@pytest.mark.parametrize("role", ["reserve", "forward", "exploration"])
def test_reconstructed_inputs_have_no_evidential_weight(role):
    assert ledger.evidential_weight("blind", role, designated=True, reconstructed=True) == 0


@pytest.mark.parametrize("dtype", ["datetime64[2D]", "datetime64[48h]"])
def test_numpy_multi_day_precision_cannot_be_promoted(dtype):
    dates = np.array(["2010-01-01"], dtype=dtype)
    with pytest.raises(pit.PitError):
        pit.PitStore().add("x", dates, [1], lag_days=0)


def test_perturbation_copies_are_never_historical_evidence():
    from manhattan.engine import lookahead
    st = pit.PitStore()
    st.add("x", ["2010-01-01", "2010-01-02"], [1, 2], lag_days=0, reconstructed=True)
    for copy in (lookahead.tampered_after(st, "2010-01-01"), lookahead.shifted(st, "x")):
        with pytest.raises(pit.PitError, match="reconstructed"):
            copy.require_historical_evidence()


def test_compiler_checks_sources_on_compile_and_rebuild():
    from test_manhattan_ops_compiler import fam, hyp
    f = fam()
    h = hyp(f, "buy_hold", grid={"scale": [1.0]})  # existing synthetic compiler fixture
    h["data_sources"] = [source()]
    assert compiler.check_hypothesis(h) == []
    compiled = next(compiler.iter_executables(f, h, "fixture"))
    assert compiler.from_specs(compiled.executable, compiled.variant, h, f).hypothesis == h
    h["data_sources"][0].pop("frequency")
    assert any("source frequency" in e for e in compiler.check_hypothesis(h))
    with pytest.raises(compiler.CompileError, match="source frequency"):
        next(compiler.iter_executables(f, h, "fixture"))
    # Rebuild with internally consistent links, so validation, not a stale hash, refuses it.
    v = spec.variants(h)[0]
    x = spec.primary_executable(h, v, "fixture")
    with pytest.raises(compiler.CompileError, match="source frequency"):
        compiler.from_specs(x, v, h, f)


def test_reconstructed_flag_is_recorded_and_forward_weight_is_zero(tmp_path, monkeypatch):
    from test_manhattan_registry import ev
    book = ledger.Ledger(tmp_path / "ledger.jsonl", writer="fixture", protocol="0" * 64)
    rec = book.record_evaluation(**ev(reconstructed=True))
    assert rec["payload"]["reconstructed"] is True
    assert rec["payload"]["evidential_weight"] == 0

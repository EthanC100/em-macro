"""Retry and fallback behaviour of the raw downloader (no network: the session is stubbed)."""
import pandas as pd
import pytest
import requests

from em_macro import sources as S


@pytest.fixture(autouse=True)
def _fresh_breaker():
    S.DOWN_HOSTS.clear()
    yield
    S.DOWN_HOSTS.clear()


class _Resp:
    def __init__(self, status, content=b"", headers=None):
        self.status_code, self.content, self.reason = status, content, "x"
        self.headers = headers or {}


def _session(monkeypatch, outcomes):
    """outcomes: list of responses or exceptions returned by successive GETs."""
    calls = []

    def get(url, timeout=None):
        calls.append(url)
        o = outcomes[min(len(calls), len(outcomes)) - 1]
        if isinstance(o, Exception):
            raise o
        return o

    monkeypatch.setattr(S.SESSION, "get", get)
    monkeypatch.setattr(S.time, "sleep", lambda s: None)
    return calls


def test_get_retries_5xx_then_succeeds(tmp_path, monkeypatch):
    calls = _session(monkeypatch, [_Resp(502), _Resp(503), _Resp(200, b"ok")])
    assert S._get("http://x/a", tmp_path / "a", refresh=True) == b"ok"
    assert len(calls) == 3 and (tmp_path / "a").read_bytes() == b"ok"


def test_get_does_not_retry_404(tmp_path, monkeypatch):
    calls = _session(monkeypatch, [_Resp(404)])
    with pytest.raises(RuntimeError, match="404"):
        S._get("http://x/missing", tmp_path / "m", refresh=True)
    assert len(calls) == 1


def test_get_retries_timeouts_and_gives_up(tmp_path, monkeypatch):
    calls = _session(monkeypatch, [requests.ReadTimeout("slow")])
    with pytest.raises(RuntimeError, match="slow"):
        S._get("http://x/hang", tmp_path / "h", refresh=True, tries=3)
    assert len(calls) == 3


def test_get_falls_back_to_stale_cache(tmp_path, monkeypatch, capsys):
    cache = tmp_path / "c"
    cache.write_bytes(b"last month")
    _session(monkeypatch, [_Resp(502)])
    assert S._get("http://x/down", cache, refresh=True, tries=2) == b"last month"
    assert "WARNING" in capsys.readouterr().err


def test_get_uses_cache_without_refresh(tmp_path, monkeypatch):
    cache = tmp_path / "c"
    cache.write_bytes(b"cached")
    calls = _session(monkeypatch, [_Resp(200, b"new")])
    assert S._get("http://x/c", cache) == b"cached" and calls == []


def test_backoff_honours_retry_after():
    assert S._backoff(0) == 2 and S._backoff(4) == 32 and S._backoff(9) == 60
    assert S._backoff(0, _Resp(429, headers={"Retry-After": "30"})) == 30
    assert S._backoff(0, _Resp(429, headers={"Retry-After": "999"})) == 120


def test_yahoo_retries_empty_then_falls_back_to_cache(tmp_path, monkeypatch):
    import yfinance as yf
    monkeypatch.setattr(S, "RAW", tmp_path)
    cache = tmp_path / "yahoo" / "TRY_X.csv"
    cache.parent.mkdir()
    pd.Series([1.0, 2.0], index=pd.to_datetime(["2024-01-01", "2024-01-02"]), name="TRY=X").to_frame().to_csv(cache)
    n = []
    monkeypatch.setattr(yf, "download", lambda *a, **k: n.append(1) or pd.DataFrame())
    monkeypatch.setattr(S.time, "sleep", lambda s: None)
    s = S.yahoo("TRY=X", refresh=True)
    assert len(n) == 3 and list(s) == [1.0, 2.0]


def test_get_retries_bad_body_and_never_caches_it(tmp_path, monkeypatch):
    html = _Resp(200, b"<html>Service Unavailable</html>")
    calls = _session(monkeypatch, [html, html, _Resp(200, b'{"ok": 1}')])
    out = S._get("http://x/j", tmp_path / "j", refresh=True, check=S._is_json)
    assert out == b'{"ok": 1}' and len(calls) == 3


def test_get_rejects_stale_copy_that_fails_check(tmp_path, monkeypatch):
    cache = tmp_path / "c"
    cache.write_bytes(b"")                                    # an empty body cached by an older version
    _session(monkeypatch, [_Resp(200, b"not json")])
    with pytest.raises(RuntimeError, match="unexpected body"):
        S._get("http://x/j", cache, refresh=True, tries=2, check=S._is_json)
    assert cache.read_bytes() == b""                          # the bad body was not written over it


def test_body_checks():
    assert S._is_json(b"[1, 2]") and not S._is_json(b"") and not S._is_json(b"<html>")
    assert S._has("TIME_PERIOD")(b"FREQ,TIME_PERIOD,OBS_VALUE\n") and not S._has("TIME_PERIOD")(b"<html>")


def test_env_flag_forces_refresh_with_fallback(tmp_path, monkeypatch):
    cache = tmp_path / "c"
    cache.write_bytes(b"cached")
    monkeypatch.setenv("EM_MACRO_REFRESH", "1")
    calls = _session(monkeypatch, [_Resp(200, b"fresh")])
    assert S._get("http://x/c", cache) == b"fresh" and len(calls) == 1
    _session(monkeypatch, [_Resp(503)])
    assert S._get("http://x/c", cache, tries=2) == b"fresh"          # fell back to the refreshed copy
    monkeypatch.delenv("EM_MACRO_REFRESH")
    calls = _session(monkeypatch, [_Resp(200, b"newer")])
    assert S._get("http://x/c", cache) == b"fresh" and calls == []   # cache-first again


def test_401_is_retried_and_host_breaker_bounds_the_cost(tmp_path, monkeypatch):
    S.DOWN_HOSTS.clear()
    calls = _session(monkeypatch, [_Resp(401)])
    with pytest.raises(RuntimeError, match="401"):
        S._get("http://imf.test/a", tmp_path / "a", refresh=True, tries=3)
    assert len(calls) == 3 and "imf.test" in S.DOWN_HOSTS
    calls = _session(monkeypatch, [_Resp(401)])
    with pytest.raises(RuntimeError):
        S._get("http://imf.test/b", tmp_path / "b", refresh=True, tries=3)
    assert len(calls) == 1                                            # one try while the host is down
    calls = _session(monkeypatch, [_Resp(200, b"back")])
    assert S._get("http://imf.test/c", tmp_path / "c", refresh=True) == b"back"
    assert "imf.test" not in S.DOWN_HOSTS                             # recovered


def test_404_does_not_mark_host_down(tmp_path, monkeypatch):
    S.DOWN_HOSTS.clear()
    _session(monkeypatch, [_Resp(404)])
    with pytest.raises(RuntimeError):
        S._get("http://fred.test/missing", tmp_path / "m", refresh=True)
    assert "fred.test" not in S.DOWN_HOSTS

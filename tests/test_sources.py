"""Retry and fallback behaviour of the raw downloader (no network: the session is stubbed)."""
import pandas as pd
import pytest
import requests

from em_macro import sources as S


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

"""Shared, cached features: the main computation reuse across parameter variants.

Every feature is a ``(T, A)`` float64 array aligned so that row ``t`` uses data through the close of day ``t`` only
(PIT: a position built from row ``t`` is applied to the return of day ``t + 1`` by the kernels, never earlier).
Rows before a feature is defined are NaN.

Thousands of candidates share a handful of features (for example every trend candidate with look-back 60 on FX
uses the same ``mom(60)``), so each is computed once per process and, optionally, persisted.

Cache keys are ``sha256(canonical({data_hash, domain, feature, params, feature_code}))``: a change of data, of the
feature's parameters or of this module's source gives a new key, so a stale entry is never read.

Disk entries are ``<key>.npy`` with a ``<key>.sha256`` sidecar. A load verifies the bytes against the sidecar;
a mismatch is *corruption*: the entry is moved aside (``.corrupt-<n>``), the feature is recomputed and the event is
returned to the runner, which logs it. A corrupt entry can therefore cost time but never change a result.
"""
from __future__ import annotations

import io
import os
import time
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from manhattan.spec import canonical_bytes

from . import data as D
from .ids import sha256_bytes

_CODE_HASH: str | None = None


def feature_code_hash() -> str:
    global _CODE_HASH
    if _CODE_HASH is None:
        _CODE_HASH = sha256_bytes(Path(__file__).read_bytes())
    return _CODE_HASH


# -- the features (pure functions of the fenced panel) --------------------------------------------------------

def _logcum(r: np.ndarray) -> np.ndarray:
    return np.cumsum(np.log1p(np.clip(r, -0.99, None)), axis=0)


def f_cum(panel, dom):
    return _logcum(panel.returns(dom))


def f_mom(panel, dom, L, cum):
    out = np.full_like(cum, np.nan)
    out[L:] = cum[L:] - cum[:-L]
    return out


def f_ewvol(panel, dom, hl, min_obs=20):
    """EWMA standard deviation of daily returns through day t (no look-ahead), NaN before ``min_obs`` days."""
    r = panel.returns(dom)
    lam = 0.5 ** (1.0 / hl)
    v = np.empty_like(r)
    acc = np.zeros(r.shape[1])
    w = 0.0
    for t in range(r.shape[0]):
        acc = lam * acc + (1.0 - lam) * r[t] * r[t]
        w = lam * w + (1.0 - lam)
        v[t] = acc / w
    out = np.sqrt(v)
    out[:min_obs] = np.nan
    return out


def f_zscore(panel, dom, L, cum):
    """(cum[t] - mean(cum[t-L+1..t])) / std(cum[t-L+1..t]): the price's position in its own recent range."""
    out = np.full_like(cum, np.nan)
    win = sliding_window_view(cum, L, axis=0)            # (T-L+1, A, L), window ends at t
    m = win.mean(axis=2)
    s = win.std(axis=2)
    with np.errstate(invalid="ignore", divide="ignore"):
        out[L - 1:] = np.where(s > 0, (cum[L - 1:] - m) / s, 0.0)
    return out


def f_hi(panel, dom, L, cum):
    out = np.full_like(cum, np.nan)
    out[L - 1:] = sliding_window_view(cum, L, axis=0).max(axis=2)
    return out


def f_lo(panel, dom, L, cum):
    out = np.full_like(cum, np.nan)
    out[L - 1:] = sliding_window_view(cum, L, axis=0).min(axis=2)
    return out


def f_carry(panel, dom, L):
    """Rolling mean of the published carry over L days (the carry is already lagged by publication)."""
    c = panel.carry(dom)
    out = np.full_like(c, np.nan)
    cc = np.nan_to_num(c, nan=0.0)
    cs = np.cumsum(cc, axis=0)
    out[L:] = (cs[L:] - cs[:-L]) / L                    # rows 1..L hold the window [t-L+1, t]; row 0 is NaN data
    return out


class FeatureCache:
    """Per-process memory cache with an optional verified disk layer. Not shared between processes in memory;
    forked workers inherit what the parent has already computed (copy-on-write)."""

    def __init__(self, panel, cache_dir: Path | None = None, enabled: bool = True):
        self.panel = panel
        self.dir = Path(cache_dir) if cache_dir else None
        self.enabled = enabled
        self.mem: dict[str, np.ndarray] = {}
        self._keys: dict[tuple, str] = {}
        self.stats = {"mem_hits": 0, "disk_hits": 0, "misses": 0, "compute_s": 0.0, "corrupt": 0}
        self.events: list[dict] = []

    def key(self, dom: str, name: str, **params) -> str:
        return sha256_bytes(canonical_bytes({"data": self.panel.data_hash, "domain": dom, "feature": name,
                                             "params": params, "code": feature_code_hash()}))

    def _disk_load(self, k: str):
        if not self.dir:
            return None
        f, s = self.dir / f"{k}.npy", self.dir / f"{k}.sha256"
        if not (f.exists() and s.exists()):
            return None
        raw = f.read_bytes()
        if sha256_bytes(raw) != s.read_text().strip():
            n = len(list(self.dir.glob(f"{k}.npy.corrupt-*")))
            os.replace(f, self.dir / f"{k}.npy.corrupt-{n}")
            self.stats["corrupt"] += 1
            self.events.append({"event": "cache_corrupt", "key": k, "quarantine": f"{k}.npy.corrupt-{n}"})
            return None
        return np.load(io.BytesIO(raw), allow_pickle=False)

    def _disk_store(self, k: str, arr: np.ndarray) -> None:
        if not self.dir:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        np.save(buf, arr, allow_pickle=False)
        raw = buf.getvalue()
        tmp = self.dir / f".{k}.npy.tmp-{os.getpid()}"
        tmp.write_bytes(raw)
        os.replace(tmp, self.dir / f"{k}.npy")
        tmp2 = self.dir / f".{k}.sha256.tmp-{os.getpid()}"
        tmp2.write_text(sha256_bytes(raw))
        os.replace(tmp2, self.dir / f"{k}.sha256")      # sidecar last: an entry without it is ignored

    def get(self, dom: str, name: str, **params) -> np.ndarray:
        if not self.enabled:
            self.stats["misses"] += 1
            t0 = time.perf_counter()
            out = self._compute(dom, name, **params)
            self.stats["compute_s"] += time.perf_counter() - t0
            return out
        t = (dom, name, tuple(sorted(params.items())))
        k = self._keys.get(t)
        if k is None:
            k = self._keys[t] = self.key(dom, name, **params)
        hit = self.mem.get(k)
        if hit is not None:
            self.stats["mem_hits"] += 1
            return hit
        arr = self._disk_load(k)
        if arr is not None:
            self.stats["disk_hits"] += 1
        else:
            self.stats["misses"] += 1
            t0 = time.perf_counter()
            arr = self._compute(dom, name, **params)
            self.stats["compute_s"] += time.perf_counter() - t0
            self._disk_store(k, arr)
        arr.setflags(write=False)
        self.mem[k] = arr
        return arr

    def _compute(self, dom: str, name: str, **p) -> np.ndarray:
        pn = self.panel
        if name == "cum":
            return f_cum(pn, dom)
        if name == "mom":
            return f_mom(pn, dom, p["L"], self.get(dom, "cum"))
        if name == "ewvol":
            return f_ewvol(pn, dom, p["hl"])
        if name == "zscore":
            return f_zscore(pn, dom, p["L"], self.get(dom, "cum"))
        if name == "hi":
            return f_hi(pn, dom, p["L"], self.get(dom, "cum"))
        if name == "lo":
            return f_lo(pn, dom, p["L"], self.get(dom, "cum"))
        if name == "carry":
            return f_carry(pn, dom, p["L"])
        if name == "unit_risk":
            vol = self.get(dom, "ewvol", hl=p["hl"])
            with np.errstate(invalid="ignore", divide="ignore"):
                f = (p["ann"] / np.sqrt(252.0)) / (vol * np.sqrt(vol.shape[1]))
            return np.nan_to_num(f, nan=0.0, posinf=0.0, neginf=0.0)
        if name == "absret":
            return np.abs(pn.returns(dom))
        raise KeyError(f"unknown feature {name!r}")


def assert_panel(panel) -> None:
    D.verify_synthetic(panel)

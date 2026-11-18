"""Point-in-time checks for templates (stage 0) and the evaluation lag contract.

**Contract.** A template's position row ``t`` may use data through the close of day ``t`` only. The kernels apply
row ``t`` to the return of day ``t + 1`` (``kernels.align``). Together these mean no position earns a return that was
known when it was set.

**Probe** (``probe``). The positions of a template are computed on a small synthetic panel and again on a copy whose
returns and carry after day ``tau`` are replaced by independent draws. Rows ``0..tau`` must be bit-identical, for
several ``tau``, every domain and the corner points of the template's schema. A template that reads any future row
fails. The probe is structural (it does not depend on any performance number) and is logged once per template
version by the registry; a failing template cannot register candidates.

The probe cannot prove the absence of look-ahead for parameter values it does not try, nor for features that are
look-ahead-free on this generator by accident. It is a strong, cheap test, not a proof.
"""
from __future__ import annotations

import itertools

import numpy as np

from . import data as D
from . import features as F
from . import templates as TP

PROBE_PARAMS = D.PanelParams(seed=4242, n_days=760, protected_days=100)
TAUS = (320, 433, 590)


def _perturbed(panel: D.FencedPanel, tau: int, seed: int) -> D.FencedPanel:
    rng = np.random.default_rng(seed)
    rets, car = {}, {}
    for d in panel.domains():
        r = np.array(panel._returns[d])
        c = np.array(panel._carry[d])
        r[tau + 1:] = rng.normal(0.0, r.std() * 3.0, size=r[tau + 1:].shape)
        c[tau + 1:] = rng.normal(0.0, 5.0, size=c[tau + 1:].shape)
        rets[d], car[d] = r, c
    # a probe-only panel: not a verified synthetic panel (it never reaches the runner)
    return D.FencedPanel(params=panel.params, data_hash="probe-" + str(tau), fence=panel.fence, dates=panel.dates,
                         _returns=rets, _carry=car, provenance={"synthetic": False, "probe": True})


def _corner_points(template: str) -> list[dict]:
    t = TP.TEMPLATES[template]
    axes = {}
    for k, (kind, *rng) in t.schema.items():
        if kind == "int":
            lo, hi = rng
            hi = min(hi, TP.MAX_LOOKBACK)
            axes[k] = sorted({lo, (lo + hi) // 2, hi})
        elif kind == "float":
            lo, hi = rng
            axes[k] = sorted({float(lo), float(lo + hi) / 2.0, float(hi)})
        else:
            axes[k] = list(rng[0])
    keys = sorted(axes)
    pts = []
    for vals in itertools.product(*(axes[k] for k in keys)):
        p = dict(zip(keys, vals))
        if not TP.validate_params(template, p):
            pts.append(p)
    # deterministic thinning: at most 24 points, spread over the product
    if len(pts) > 24:
        step = len(pts) / 24.0
        pts = [pts[int(i * step)] for i in range(24)]
    return pts


_MEMO: dict = {}


def code_hash() -> str:
    """SHA-256 of the template and feature code a probe result depends on."""
    from pathlib import Path
    from .ids import sha256_bytes
    return sha256_bytes(Path(TP.__file__).read_bytes() + Path(F.__file__).read_bytes())


def probe(template: str, panel: D.FencedPanel | None = None) -> dict:
    """Run (or reuse, within one process, for unchanged template and feature code) the probe of one template."""
    code = code_hash()
    key = (template, TP.TEMPLATES[template].version, id(TP.TEMPLATES[template]), code,
           panel.data_hash if panel is not None else "default")
    if key not in _MEMO:
        _MEMO[key] = _probe(template, panel)
    return dict(_MEMO[key])


def _probe(template: str, panel: D.FencedPanel | None = None) -> dict:
    base = panel if panel is not None else D.generate(PROBE_PARAMS)
    pts = _corner_points(template)
    taus = [t for t in TAUS if t < base.fence - 2]
    failures = []
    checks = 0
    base_cache = F.FeatureCache(base)
    for j, tau in enumerate(taus):
        pert = _perturbed(base, tau, seed=1000 + j)
        pc = F.FeatureCache(pert)
        for dom in base.domains():
            for p in pts:
                for sizing in TP.SIZINGS:
                    try:
                        a = TP.positions(base_cache, template, dom, p, sizing)
                        b = TP.positions(pc, template, dom, p, sizing)
                    except Exception as e:          # a template that cannot run its own corner points fails
                        failures.append({"tau": tau, "domain": dom, "params": p, "sizing": sizing,
                                         "error_class": type(e).__name__})
                        return {"passed": False, "checks": checks, "failures": failures}
                    checks += 1
                    if not np.array_equal(a[: tau + 1], b[: tau + 1], equal_nan=True):
                        bad = int(np.argmax(np.any(a[: tau + 1] != b[: tau + 1], axis=1)))
                        failures.append({"tau": tau, "domain": dom, "params": p, "sizing": sizing,
                                         "first_row": bad})
                        if len(failures) >= 5:
                            return {"passed": False, "checks": checks, "failures": failures}
    return {"passed": not failures, "checks": checks, "failures": failures}

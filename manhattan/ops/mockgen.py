"""The blind request (template v2) and a mock generator for tests (criteria O-13, O-34).

``blind_request`` is the ops adapter of ``manhattan.generate.blind_request`` for template v2 (which adds the
variant-justification and timing fields). Its signature is the fence: there is no argument through which a result,
a ledger record, a path or free text can reach the prompt.

``mock_reply`` answers a request without any model: it returns ``n`` families marked **SYNTHETIC**, built from a
seeded random generator and the request's own hash. They are placeholders that exercise the pipeline, never
research hypotheses, and are only ever bound to the synthetic universe.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from manhattan import spec as S
from manhattan.generate import GenerationError, Request

from . import compiler, justify, timing

TEMPLATES = Path(__file__).resolve().parent / "templates"
TEMPLATE = "blind_v2.md"


def template_text(name: str = TEMPLATE) -> tuple[str, str]:
    data = (TEMPLATES / name).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    recorded = dict(line.split()[::-1] for line in (TEMPLATES / "templates.sha256").read_text().splitlines() if line.strip())
    if recorded.get(name) != digest:
        raise GenerationError(f"{name} does not match its recorded hash: a template is never edited, only versioned")
    return data.decode("utf-8"), digest


def blind_request(*, n_families: int, max_hypotheses: int, domains: tuple[str, ...]) -> Request:
    if isinstance(n_families, bool) or not isinstance(n_families, int) or not 1 <= n_families <= 100:
        raise GenerationError("n_families must be a whole number from 1 to 100")
    if isinstance(max_hypotheses, bool) or not isinstance(max_hypotheses, int) or not 1 <= max_hypotheses <= 10:
        raise GenerationError("max_hypotheses must be a whole number from 1 to 10")
    if not domains or any(not isinstance(d, str) or not d.replace("_", "").isalnum() for d in domains):
        raise GenerationError("domains are plain identifiers such as fx_daily")
    text, digest = template_text()
    prompt = text.format(n_families=n_families, max_hypotheses=max_hypotheses, domains=", ".join(sorted(domains)),
                         mechanism_classes=", ".join(S.MECHANISM_CLASSES), max_grid=S.MAX_GRID,
                         signal_kinds=", ".join(sorted(compiler.KINDS)), universes=", ".join(sorted(compiler.UNIVERSES)),
                         cost_models=", ".join(sorted(compiler.COST_MODELS)), sizings=", ".join(sorted(compiler.SIZING)),
                         budget=justify.DEFAULT_BUDGET, calendars=", ".join(sorted(timing.CALENDARS)))
    return Request("blind", TEMPLATE, digest, prompt)


# ---------------------------------------------------------------- the mock generator (tests only)

_PLAN = [  # (kind, frequency, fixed, grid, justification ranges)
    ("tsmom", "D", {}, {"lookback": [20, 60, 120]}, {"lookback": [20, 120]}),
    ("xs_momentum", "W", {"n_long": 2}, {"lookback": [20, 60]}, {"lookback": [20, 60]}),
    ("reversal", "D", {}, {"lookback": [2, 5, 10]}, {"lookback": [1, 10]}),
    ("carry", "M", {}, {"threshold": [0.0, 0.01]}, {"threshold": [0, 0.02]}),
    ("calendar", "D", {"end_day": 28}, {"start_day": [20, 24]}, {"start_day": [18, 26]}),
    ("event", "event", {}, {"hold": [3, 5]}, {"hold": [2, 6]}),
    ("buy_hold", "M", {}, {"scale": [1.0]}, {}),
    ("tsmom", "W", {}, {"lookback": [60, 120]}, {"lookback": [40, 160]}),
    ("xs_momentum", "M", {"lookback": 120}, {"n_long": [1, 2]}, {"n_long": [1, 2]}),
    ("carry", "W", {}, {"threshold": [0.005]}, {}),
]


def mock_reply(request: Request, *, n: int = 10, seed: int = 0, declared: dict | None = None) -> str:
    """A reply in the shape the template asks for: ``n`` SYNTHETIC families, one or two hypotheses each.
    ``declared`` maps a family index to a declared first observation (tests use it to make late predictions)."""
    rng = np.random.default_rng(int(request.prompt_hash[:8], 16) ^ seed)
    fams = []
    for i in range(n):
        kind, freq, fixed, grid, rngs = _PLAN[i % len(_PLAN)]
        tag = f"SYNTHETIC TEST FAMILY {i + 1:02d}"
        fam = {"mechanism": f"{tag}: placeholder mechanism for pipeline tests; not a research hypothesis",
               "mechanism_class": S.MECHANISM_CLASSES[i % len(S.MECHANISM_CLASSES)],
               "sign": "+" if rng.random() < 0.5 else "-",
               "counterparty": f"{tag}: synthetic counterparty", "kill_condition": f"{tag}: synthetic kill condition",
               "tail_exposure": "none declared (synthetic)"}
        hyps = []
        for k in range(1 if i % 3 else 2):
            sizing = "VT10" if k else "EW"
            h = {"domain": "syn_daily",
                 "data_sources": [{"name": "synthetic_prices", "publication_lag_days": 0},
                                  {"name": "synthetic_carry", "publication_lag_days": 1}],
                 "signal": {"kind": kind, "description": f"{tag}: synthetic {kind} signal", **fixed},
                 "frequency": freq,
                 "primary_binding": {"universe_id": "U_SYN6", "cost_model_id": "C2BP", "sizing_id": sizing},
                 "grid": grid,
                 "grid_justification": {p: {"reason": f"{tag}: synthetic reason; the mechanism's timescale for {p} is uncertain",
                                            "mechanism_range": r} for p, r in rngs.items()},
                 "timing": {"calendar": "synthetic", "horizon_sessions": compiler.NATURAL_HORIZON[freq],
                            "execution_lag": {"minutes": 0, "sessions": 0}, "data_cutoff": "2019-12-31"}}
            if declared and i in declared:
                h["timing"]["declared_first_observation"] = declared[i]
            hyps.append(h)
        fams.append({"family": fam, "hypotheses": hyps})
    return json.dumps({"families": fams}, sort_keys=True)

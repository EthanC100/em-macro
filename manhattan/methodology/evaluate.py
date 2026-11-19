"""Run the across-family procedures over a synthetic programme and count errors per unit and per class.

Procedures (the first two are Protocol v3.1 §4.3 and §4.4, called from ``manhattan.stats.screening`` unchanged):

    bh_prds      candidate (i), Batch-BH^PRDS on the units' p-values, batch by batch
    ebh_elond    candidate (ii), e-BH inside the batch at e-LOND's level, on the units' e-values
    offline_bh   Benjamini-Hochberg once over every unit of the programme at level α: **not admissible** (the
                 programme is not known in advance, and it needs PRDS across all units); a reference for how much
                 power the online schedule costs

``dedup=True`` is the remedy tested in S13: only the **first** unit of each scientific class (in batch order) is
shown to the procedure; the other units of the class are recorded and inherit the class's decision but are never
tested, so they enter no count, no denominator and no reward.

Two error counts are kept, because they answer different questions:

    unit level   V / R over registered units, what the procedures' theorems are about
    class level  V / R over scientific classes, a class counting once when any of its units is rejected: what a
                 scientific reader means by "how many of our discoveries are false"
"""
from __future__ import annotations

import numpy as np

from manhattan.stats import screening

from .worlds import Draw

PROCEDURES = ("bh_prds", "ebh_elond", "offline_bh")


def _bh(p: np.ndarray, alpha: float) -> np.ndarray:
    n = p.size
    order = np.argsort(p, kind="stable")
    ok = p[order] <= np.arange(1, n + 1) * alpha / n
    k = int(np.flatnonzero(ok).max() + 1) if ok.any() else 0
    out = np.zeros(n, dtype=bool)
    out[order[:k]] = True
    return out


def tested_mask(d: Draw, dedup: bool) -> np.ndarray:
    if not dedup:
        return np.ones(d.unit_class.size, dtype=bool)
    _, first = np.unique(d.unit_class, return_index=True)      # arrays are in batch order
    out = np.zeros(d.unit_class.size, dtype=bool)
    out[first] = True
    return out


def screen(d: Draw, procedure: str, *, B: int, N: int = 120, alpha: float = screening.ALPHA_S,
           dedup: bool = False) -> np.ndarray:
    """Boolean mask of rejected units. Untested units (``dedup``) are never rejected themselves."""
    test = tested_mask(d, dedup)
    rej = np.zeros(d.unit_class.size, dtype=bool)
    if procedure == "offline_bh":
        idx = np.flatnonzero(test)
        rej[idx] = _bh(d.p[idx], alpha)
        return rej
    proc = {"bh_prds": screening.BatchBH, "ebh_elond": screening.EbhElond}[procedure](N, alpha)
    stat = d.p if procedure == "bh_prds" else d.E
    for b in range(B):
        idx = np.flatnonzero((d.unit_batch == b) & test)
        dec = proc.step(stat[idx])
        rej[idx] = dec.rejected
    return rej


def counts(d: Draw, rej: np.ndarray, B: int) -> dict:
    """End-of-programme and per-batch-end errors, at unit and class level."""
    false_unit = ~d.class_true[d.unit_class]
    R_u, V_u = int(rej.sum()), int((rej & false_unit).sum())
    n_cls = d.class_true.size
    first_rej = np.full(n_cls, B, dtype=np.int64)              # batch of a class's first rejection (B: never)
    np.minimum.at(first_rej, d.unit_class[rej], d.unit_batch[rej])
    cls_rej = first_rej < B
    R_c, V_c = int(cls_rej.sum()), int((cls_rej & ~d.class_true).sum())
    n_true = int(d.class_true.sum())
    # per batch end: cumulative unit and class counts
    ub = np.bincount(d.unit_batch[rej], minlength=B)
    vb = np.bincount(d.unit_batch[rej & false_unit], minlength=B)
    cb = np.bincount(first_rej[cls_rej], minlength=B)
    cvb = np.bincount(first_rej[cls_rej & ~d.class_true], minlength=B)
    Ru, Vu, Rc, Vc = (np.cumsum(x)[:B] for x in (ub, vb, cb, cvb))
    return {
        "R_unit": R_u, "V_unit": V_u, "fdp_unit": V_u / max(R_u, 1),
        "R_class": R_c, "V_class": V_c, "fdp_class": V_c / max(R_c, 1),
        "true_classes": n_true, "power_class": (R_c - V_c) / n_true if n_true else float("nan"),
        "fdp_unit_path": Vu / np.maximum(Ru, 1), "fdp_class_path": Vc / np.maximum(Rc, 1),
    }


def summarise(rows: list[dict]) -> dict:
    """Mean over replications, with a normal 95% interval half-width for the FDRs and power."""
    out = {"reps": len(rows)}
    for key in ("fdp_unit", "fdp_class", "power_class", "R_unit", "R_class", "V_unit", "V_class"):
        x = np.array([r[key] for r in rows], dtype=float)
        x = x[np.isfinite(x)]
        if x.size == 0:
            out[key] = None
            continue
        name = {"fdp_unit": "fdr_unit", "fdp_class": "fdr_class"}.get(key, key)
        out[name] = float(x.mean())
        if key in ("fdp_unit", "fdp_class", "power_class"):
            out[name + "_hw"] = float(1.96 * x.std(ddof=1) / np.sqrt(x.size)) if x.size > 1 else None
    for key in ("fdp_unit_path", "fdp_class_path"):
        path = np.mean([r[key] for r in rows], axis=0)
        out["max_batch_end_" + key.replace("fdp", "fdr").replace("_path", "")] = float(path.max())
    out["any_false_unit"] = float(np.mean([r["V_unit"] > 0 for r in rows]))
    out["any_false_class"] = float(np.mean([r["V_class"] > 0 for r in rows]))
    return out

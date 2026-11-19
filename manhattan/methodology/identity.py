"""Three identity layers and the population census (S13 methodology, priorities 1 and 2).

Manhattan needs three identities that must never be folded into one:

    scientific   WHAT is claimed: family (mechanism, sign, counterparty), hypothesis (domain, signal), variant
                 (grid point). Content-addressed by ``manhattan.spec``. Multiplicity is counted here, after
                 duplicates are merged into **scientific classes**.
    evaluation   WHICH look at the evidence: a scientific object bound to a universe, cost and sizing, a
                 methodology, a window and a data role. A *look* is ``(scientific, binding, methodology, window,
                 role)``; a *computation* adds the data hash, the code version and the numerical environment.
                 Repeated computations of one look are reruns (same result) or nondeterminism (different result);
                 a changed data hash or code version on the same look is a **repeated look** of the same object.
    scheduling   HOW the work was done: chunk, attempt, worker, order, retry. It must change neither a result nor
                 a count. Its only role in accounting is that every attempt has exactly one terminal, so that
                 failures and interruptions are visible.

The census below is a pure function of records in that layered shape. It never computes a statistic, and it never
turns a count into a multiplicity correction by itself: it reports the denominators a procedure must be told and
the violations that make a statistic descriptive. It is a specification in code, independent of the stores that
would feed it (PR #86's Ledger, HTE's attempt log); wiring it to them is an owner decision (PR #86 D-1, D-10).
"""
from __future__ import annotations

import hashlib
from collections import Counter, defaultdict

from manhattan.spec import canonical_bytes

SCIENTIFIC_LEVELS = ("family", "hypothesis", "variant")
LOOK_FIELDS = ("binding", "methodology", "window", "role")
COMPUTATION_FIELDS = ("data_hash", "code", "env")
SCHEDULE_FIELDS = ("attempt", "chunk", "worker", "order", "status", "supersedes", "result_hash", "seq",
                   "data_read", "started", "finished")
STATUSES = ("completed", "failed", "aborted", "unfinished")


class LayerError(ValueError):
    """A field of one identity layer was found in another."""


def _h(obj) -> str:
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()


def scientific_key(sci: dict) -> str:
    """Hash of the scientific identity. Refuses evaluation and scheduling fields: a code version, a data hash or a
    worker inside a scientific identity would turn one claim into many."""
    bad = set(sci) & (set(LOOK_FIELDS) | set(COMPUTATION_FIELDS) | set(SCHEDULE_FIELDS))
    if bad:
        raise LayerError(f"scientific identity holds non-scientific fields: {sorted(bad)}")
    missing = [lv for lv in SCIENTIFIC_LEVELS if lv not in sci]
    if missing:
        raise LayerError(f"scientific identity lacks {missing}")
    return _h(sci)


def look_key(sci: dict, ev: dict) -> str:
    """One look: the scientific object, its binding and methodology, on one window in one role."""
    bad = set(ev) & set(SCHEDULE_FIELDS)
    if bad:
        raise LayerError(f"evaluation identity holds scheduling fields: {sorted(bad)}")
    missing = [f for f in LOOK_FIELDS if f not in ev]
    if missing:
        raise LayerError(f"evaluation identity lacks {missing}")
    return _h({"scientific": scientific_key(sci), **{f: ev[f] for f in LOOK_FIELDS}})


def computation_key(sci: dict, ev: dict) -> str:
    """One computation of a look: the look plus data hash, code version and numerical environment."""
    missing = [f for f in COMPUTATION_FIELDS if f not in ev]
    if missing:
        raise LayerError(f"evaluation identity lacks {missing}")
    return _h({"look": look_key(sci, ev), **{f: ev[f] for f in COMPUTATION_FIELDS}})


def merge_classes(families, keys: dict) -> dict:
    """Scientific classes: families merged when they share **any** equivalence key, transitively (union-find).

    ``keys[family]`` is an iterable of equivalence keys, for example a semantic digest of the declared economics
    (family and hypothesis text excluded) and an outcome-blind behavioural fingerprint (positions only). Returns
    ``{family: class id}``; the class id is the smallest family id in the class, so it does not depend on order.
    """
    families = sorted(set(families))
    parent = {f: f for f in families}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    owner: dict = {}
    for f in families:
        for k in sorted(keys.get(f, ())):
            if k in owner:
                a, b = find(owner[k]), find(f)
                if a != b:
                    parent[max(a, b)] = min(a, b)
            else:
                owner[k] = f
    return {f: find(f) for f in families}


def census(records, classes: dict | None = None) -> dict:
    """Count a research population at every level, from layered records.

    Each record is ``{"scientific": {...}, "evaluation": {...}, "schedule": {...}, "designated": bool}`` for one
    attempt. ``schedule.status`` is one of ``STATUSES``; ``schedule.data_read`` (default True) says whether the
    attempt read evaluation data, which makes it a look even if it failed; ``schedule.supersedes`` lists attempt
    ids it retries. ``classes`` maps family id to scientific class (``merge_classes``); default: each family is
    its own class.

    Returned denominators are counts, never corrections. ``violations`` lists what makes a statistic of record
    descriptive: more than one designated look per (class, window, role), nondeterministic reruns, repeated looks
    with a changed data hash or code, and attempts without a terminal.
    """
    classes = classes or {}
    status = Counter()
    by_attempt: dict = {}
    looks: dict = {}
    comps: dict = defaultdict(set)
    designated: dict = defaultdict(set)
    accessed_units: dict = defaultdict(set)
    sci = {lv: set() for lv in SCIENTIFIC_LEVELS}
    superseded: set = set()
    violations: list = []

    for r in records:
        s, ev, sch = r["scientific"], r["evaluation"], r["schedule"]
        st = sch.get("status")
        if st not in STATUSES:
            raise ValueError(f"unknown status {st!r}")
        att = sch.get("attempt")
        if att in by_attempt:
            violations.append({"kind": "duplicate_attempt_record", "attempt": att})
            continue
        by_attempt[att] = st
        status[st] += 1
        superseded.update(sch.get("supersedes", ()))
        for lv in SCIENTIFIC_LEVELS:
            sci[lv].add(s[lv])
        if not sch.get("data_read", True):
            continue
        lk, ck = look_key(s, ev), computation_key(s, ev)
        cls = classes.get(s["family"], s["family"])
        unit = (ev["window"], ev["role"])
        looks.setdefault(lk, {"class": cls, "unit": unit})
        accessed_units[unit].add(cls)
        if st == "completed":
            comps[(lk, ck)].add(sch.get("result_hash"))
        if r.get("designated") and st == "completed":
            designated[(cls,) + unit].add(lk)

    per_look_comps = Counter(lk for lk, _ in comps)
    for (lk, ck), results in comps.items():
        if len(results) > 1:
            violations.append({"kind": "nondeterminism", "look": lk, "computation": ck})
    for lk, n in per_look_comps.items():
        if n > 1:
            violations.append({"kind": "repeated_look", "look": lk, "computations": n})
    for key, lks in designated.items():
        if len(lks) > 1:
            violations.append({"kind": "multiple_designated_looks", "class": key[0], "window": key[1],
                               "role": key[2], "looks": len(lks)})
    open_attempts = [a for a, st in by_attempt.items() if st == "unfinished" and a not in superseded]
    for a in open_attempts:
        violations.append({"kind": "unfinished_attempt", "attempt": a})

    fam_per_class = Counter(classes.get(f, f) for f in sci["family"])
    return {
        "attempts": {"registered": len(by_attempt), **{k: status[k] for k in STATUSES},
                     "balanced": len(by_attempt) == sum(status[k] for k in STATUSES),
                     "superseded": len(superseded & set(by_attempt))},
        "scientific": {lv: len(sci[lv]) for lv in SCIENTIFIC_LEVELS} | {"classes": len(fam_per_class),
                       "families_merged_into_other_classes": sum(n - 1 for n in fam_per_class.values())},
        "looks": len(looks),
        "computations": len(comps),
        "multiplicity_units": {f"{w}|{role}": len(c) for (w, role), c in sorted(accessed_units.items())},
        "violations": violations,
    }

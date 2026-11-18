"""The immutable candidate registry (stage 0: static validation, canonical identity, deduplication).

Levels (docs/manhattan/hte/ARCHITECTURE.md section 2; never silently equated):

    family          HF-  a mechanism with a predicted sign                  (synthetic labels in benchmarks)
    hypothesis      HH-  the family in one domain                           contains the family's full hash
    strategy spec   HS-  a template plus its declared, bounded grid          contains the hypothesis's full hash
    variant         HV-  one grid point                                     contains the spec's full hash
    candidate       HC-  a variant bound to a cost model and a sizing rule, under a methodology version

A child holds its parent's full hash, so no link can change without changing the child's identity.

**Append-only.** ``submit`` validates whole strategy specs; a valid new spec is enumerated and written as a
*segment* (an atomic, hash-verified file) whose SHA-256, candidate count and Merkle root are logged. Nothing is ever
removed or rewritten: a candidate that performs badly stays registered. Rejected submissions are logged with their
reasons. Re-submitting a registered spec registers nothing and logs a ``duplicate_submission``.

**Freeze.** ``freeze`` fixes the canonical evaluation order of every registered candidate (sorted by the strategy
spec's full hash, then grid index: independent of submission order, and grouping candidates that share features) and
logs the Merkle root over the candidates' full hashes in that order. A run evaluates exactly one frozen version.
Specs submitted after a run has looked at their family are flagged ``post_look`` by the packages (stage 4).

**Static validation** checks the family, hypothesis and spec records, the template, every grid value against the
template schema, duplicate grid values (they would create duplicate candidates) and the look-back limit, and runs the
template's PIT probe once per template version (``pit.probe``): a template whose positions change when only future
returns change is refused.
"""
from __future__ import annotations

import itertools
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import METHODOLOGY
from . import data as D
from . import ids, pit, store
from . import templates as TP
from .log import AttemptLog


class RegistryError(RuntimeError):
    pass


# -- record builders -----------------------------------------------------------------------------------------

def family(name: str, mechanism: str, sign: str, density: str) -> dict:
    return {"level": "family", "name": name, "mechanism": mechanism, "sign": sign, "density": density,
            "synthetic": True}


def hypothesis(fam: dict, domain: str, frequency: str = "daily") -> dict:
    return {"level": "hypothesis", "family": ids.full_hash(fam), "domain": domain, "frequency": frequency,
            "synthetic": True}


def strategy_spec(hyp: dict, template: str, grid: dict, *, cost_models=("c1",), sizings=("unit_risk",),
                  label: str = "") -> dict:
    t = TP.TEMPLATES[template]
    return {"level": "strategy_spec", "hypothesis": ids.full_hash(hyp), "template": template,
            "template_version": t.version, "label": label,
            "grid": {k: list(grid[k]) for k in sorted(grid)},
            "bindings": {"cost_model": list(cost_models), "sizing": list(sizings)}}


def grid_size(spec: dict) -> int:
    n = 1
    for k in spec["grid"]:
        n *= len(spec["grid"][k])
    return n * len(spec["bindings"]["cost_model"]) * len(spec["bindings"]["sizing"])


def point(spec: dict, gi: int) -> tuple[dict, str, str]:
    """Grid index -> (params, cost_model, sizing). Bindings vary fastest, then the last parameter (sorted)."""
    b = spec["bindings"]
    nc, ns = len(b["cost_model"]), len(b["sizing"])
    si = gi % ns
    gi //= ns
    ci = gi % nc
    gi //= nc
    keys = sorted(spec["grid"])
    params = {}
    for k in reversed(keys):
        vals = spec["grid"][k]
        params[k] = vals[gi % len(vals)]
        gi //= len(vals)
    return {k: params[k] for k in keys}, b["cost_model"][ci], b["sizing"][si]


def candidate_record(variant_hash: str, cost_model: str, sizing: str) -> dict:
    return {"level": "candidate", "variant": variant_hash, "cost_model": cost_model, "sizing": sizing,
            "methodology": METHODOLOGY}


def variant_record(spec_hash: str, params: dict) -> dict:
    return {"level": "variant", "spec": spec_hash, "params": params}


@dataclass(frozen=True)
class Bundle:
    family: dict
    hypothesis: dict
    spec: dict


# -- validation ----------------------------------------------------------------------------------------------

def validate_bundle(b: Bundle) -> list[str]:
    probs = []
    f, h, s = b.family, b.hypothesis, b.spec
    for rec, lvl, req in ((f, "family", ("name", "mechanism", "sign", "density")),
                          (h, "hypothesis", ("family", "domain", "frequency")),
                          (s, "strategy_spec", ("hypothesis", "template", "template_version", "grid", "bindings"))):
        if not isinstance(rec, dict) or rec.get("level") != lvl:
            return [f"{lvl}: not a {lvl} record"]
        missing = [k for k in req if k not in rec]
        if missing:
            probs.append(f"{lvl}: missing {missing}")
        if rec.get("synthetic") is False:
            probs.append(f"{lvl}: HTE registers synthetic research workloads only")
    if probs:
        return probs
    try:
        if h["family"] != ids.full_hash(f):
            probs.append("hypothesis.family is not the family's full hash")
        if s["hypothesis"] != ids.full_hash(h):
            probs.append("strategy_spec.hypothesis is not the hypothesis's full hash")
    except Exception as e:                      # not canonicalisable (NaN, unsupported type, ...)
        return [f"not canonicalisable: {type(e).__name__}"]
    if f["sign"] not in ("+", "-"):
        probs.append("family.sign must be + or -")
    if h["domain"] not in D.DOMAINS:
        probs.append(f"hypothesis.domain {h['domain']!r} unknown")
    if h["frequency"] != "daily":
        probs.append("only daily frequency is implemented")
    t = TP.TEMPLATES.get(s["template"])
    if t is None:
        return probs + [f"unknown template {s['template']!r}"]
    if s["template_version"] != t.version:
        probs.append(f"template version {s['template_version']} is not the implemented {t.version}")
    grid, bind = s["grid"], s["bindings"]
    if not isinstance(grid, dict) or set(grid) != set(t.schema):
        return probs + [f"grid keys {sorted(grid) if isinstance(grid, dict) else grid} != schema {sorted(t.schema)}"]
    for k, vals in grid.items():
        if not isinstance(vals, list) or not vals:
            probs.append(f"grid.{k}: a non-empty list is required")
            continue
        canon = [json.dumps(ids.full_hash({"v": v})) for v in vals] if all(
            _canonicalisable(v) for v in vals) else None
        if canon is None:
            probs.append(f"grid.{k}: a value cannot be canonicalised")
        elif len(set(canon)) != len(canon):
            probs.append(f"grid.{k}: duplicate values (would register duplicate candidates)")
    for k, allowed in (("cost_model", tuple(TP.COST_MODELS)), ("sizing", TP.SIZINGS)):
        vals = bind.get(k) if isinstance(bind, dict) else None
        if not vals or any(v not in allowed for v in vals) or len(set(vals)) != len(vals):
            probs.append(f"bindings.{k} must be distinct values from {allowed}")
    return probs


def _canonicalisable(v) -> bool:
    try:
        ids.full_hash({"v": v})
        return True
    except Exception:
        return False


# -- the registry --------------------------------------------------------------------------------------------

class Registry:
    def __init__(self, root: Path, log: AttemptLog):
        self.root = Path(root)
        self.log = log
        self.root.mkdir(parents=True, exist_ok=True)
        self.records: dict[str, dict] = {}         # full hash -> family / hypothesis / spec record
        self.spec_hashes: list[str] = []            # global spec index -> spec hash
        self.segments: list[dict] = []
        self._load()

    # loading verifies every file against the log
    def _load(self) -> None:
        for rec in self.log.of_type("registry_segment"):
            p = rec["payload"]
            raw = store.read_verified(self.root / p["records_file"], p["records_sha256"])
            on_disk = {}
            for line in raw.decode().splitlines():
                r = json.loads(line)
                on_disk[ids.full_hash(r)] = r
            for h in p["new_records"]:
                if h not in on_disk:
                    raise RegistryError(f"record {h[:16]} named in the log is missing from {p['records_file']}")
                self.records[h] = on_disk[h]
            self.spec_hashes.extend(p["new_specs"])
            self.segments.append(p)
        self._cand = None

    def _arrays(self) -> dict:
        if self._cand is None:
            parts = [store.read_arrays(self.root / s["file"], s["sha256"]) for s in self.segments]
            if parts:
                self._cand = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
            else:
                self._cand = {"spec_index": np.zeros(0, np.int32), "grid_index": np.zeros(0, np.int64),
                              "cand": np.zeros((0, 32), np.uint8), "variant": np.zeros((0, 32), np.uint8)}
        return self._cand

    def __len__(self) -> int:
        return int(sum(s["n_candidates"] for s in self.segments))

    def spec(self, i: int) -> dict:
        return self.records[self.spec_hashes[i]]

    # -- submission --------------------------------------------------------------------------------------
    def submit(self, bundles: list[Bundle], *, probe_panel=None) -> dict:
        """Validate and register. Returns counts; every outcome is logged."""
        report = {"submitted": len(bundles), "registered_specs": 0, "registered_candidates": 0,
                  "duplicate_submissions": 0, "rejected": 0}
        known_specs = set(self.spec_hashes)
        new_records, new_specs, seg_parts = [], [], []
        batch_specs: set[str] = set()
        probed = {(r["payload"]["template"], r["payload"]["version"]): r["payload"]["passed"]
                  for r in self.log.of_type("pit_probe")}
        for b in bundles:
            probs = validate_bundle(b)
            sh = None
            if not probs:
                sh = ids.full_hash(b.spec)
                key = (b.spec["template"], b.spec["template_version"])
                if key not in probed:
                    res = pit.probe(b.spec["template"], panel=probe_panel)
                    self.log.append("pit_probe", {"template": key[0], "version": key[1], **res})
                    probed[key] = res["passed"]
                if not probed[key]:
                    probs.append("template failed the PIT probe (positions depend on future data)")
            if not probs:
                bad = self._validate_points(b.spec)
                probs.extend(bad)
            if probs:
                report["rejected"] += 1
                try:
                    h = ids.full_hash(b.spec) if isinstance(b.spec, dict) else None
                except Exception:
                    h = None
                self.log.append("submission_rejected", {"spec_hash": h, "reasons": probs[:20],
                                                        "n_reasons": len(probs)})
                continue
            if sh in known_specs or sh in batch_specs:
                report["duplicate_submissions"] += 1
                self.log.append("duplicate_submission", {"spec_hash": sh})
                continue
            batch_specs.add(sh)
            for rec in (b.family, b.hypothesis, b.spec):
                h = ids.full_hash(rec)
                if h not in self.records and h not in {x[0] for x in new_records}:
                    new_records.append((h, rec))
            spec_index = len(self.spec_hashes) + len(new_specs)
            new_specs.append(sh)
            seg_parts.append(self._enumerate(b.spec, sh, spec_index))
            report["registered_specs"] += 1
        if new_specs:
            arrays = {k: np.concatenate([p[k] for p in seg_parts]) for k in seg_parts[0]}
            report["registered_candidates"] = int(arrays["spec_index"].size)
            self._commit_segment(new_records, new_specs, arrays)
        return report

    def _validate_points(self, spec: dict) -> list[str]:
        t = spec["template"]
        keys = sorted(spec["grid"])
        bad = []
        for vals in itertools.product(*(spec["grid"][k] for k in keys)):
            probs = TP.validate_params(t, dict(zip(keys, vals)))
            if probs:
                bad.append(f"point {dict(zip(keys, vals))}: {'; '.join(probs)}")
                if len(bad) >= 5:
                    break
        return bad

    def _enumerate(self, spec: dict, sh: str, spec_index: int) -> dict:
        keys = sorted(spec["grid"])
        b = spec["bindings"]
        n = grid_size(spec)
        cand = np.empty((n, 32), np.uint8)
        var = np.empty((n, 32), np.uint8)
        i = 0
        for vals in itertools.product(*(spec["grid"][k] for k in keys)):
            vh = ids.full_hash(variant_record(sh, dict(zip(keys, vals))))
            vb = np.frombuffer(bytes.fromhex(vh), np.uint8)
            for c in b["cost_model"]:
                for s in b["sizing"]:
                    cand[i] = np.frombuffer(bytes.fromhex(ids.full_hash(candidate_record(vh, c, s))), np.uint8)
                    var[i] = vb
                    i += 1
        return {"spec_index": np.full(n, spec_index, np.int32), "grid_index": np.arange(n, dtype=np.int64),
                "cand": cand, "variant": var}

    def _commit_segment(self, new_records, new_specs, arrays) -> None:
        # a full-hash collision check against everything registered (16-hex short IDs may collide; full hashes
        # are compared)
        existing = self._arrays()["cand"]
        allc = np.concatenate([existing, arrays["cand"]])
        if np.unique(allc, axis=0).shape[0] != allc.shape[0]:
            raise RegistryError("candidate full-hash collision: refusing to register")
        k = len(self.segments)
        fname = f"segment-{k:05d}.bin"
        sha = store.write_arrays(self.root / fname, arrays)
        rname = f"records-{k:05d}.jsonl"
        rsha = store.atomic_write_bytes(self.root / rname, "".join(
            json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n" for _, rec in new_records).encode())
        # files first, log record last: a crash before the record leaves orphan files that are never read
        payload = {"segment": k, "file": fname, "sha256": sha, "records_file": rname, "records_sha256": rsha,
                   "n_candidates": int(arrays["spec_index"].size),
                   "merkle_root": ids.merkle_root_array(arrays["cand"]),
                   "new_records": [h for h, _ in new_records], "new_specs": new_specs}
        self.log.append("registry_segment", payload)
        for h, rec in new_records:
            self.records[h] = rec
        self.spec_hashes.extend(new_specs)
        self.segments.append(payload)
        self._cand = None

    # -- freezing ----------------------------------------------------------------------------------------
    def freeze(self) -> dict:
        """Fix the canonical order of every registered candidate and log its root. Idempotent: freezing an
        unchanged registry returns the existing version."""
        a = self._arrays()
        n = a["spec_index"].size
        if n == 0:
            raise RegistryError("nothing registered")
        spec_rank = np.argsort(np.array(self.spec_hashes), kind="stable")
        rank_of = np.empty_like(spec_rank)
        rank_of[spec_rank] = np.arange(spec_rank.size)
        order = np.lexsort((a["grid_index"], rank_of[a["spec_index"]]))
        root = ids.merkle_root_array(a["cand"][order])
        for r in self.log.of_type("registry_frozen"):
            if r["payload"]["root"] == root and r["payload"]["n_candidates"] == n:
                return r["payload"]
        k = len(self.log.of_type("registry_frozen"))
        fname = f"frozen-{k:04d}.bin"
        sha = store.write_arrays(self.root / fname, {"order": order.astype(np.int64)})
        counts = self.level_counts()
        payload = {"version": k, "root": root, "n_candidates": int(n), "order_file": fname, "order_sha256": sha,
                   "segments": len(self.segments), "counts": counts}
        self.log.append("registry_frozen", payload)
        return payload

    def frozen(self, version: int | None = None) -> "FrozenView":
        fr = self.log.of_type("registry_frozen")
        if not fr:
            raise RegistryError("registry has not been frozen")
        p = fr[-1]["payload"] if version is None else fr[version]["payload"]
        order = store.read_arrays(self.root / p["order_file"], p["order_sha256"])["order"]
        a = self._arrays()
        if order.size != p["n_candidates"]:
            raise RegistryError("frozen order does not match its record")
        view = FrozenView(self, p, order, {k: v[: p["n_candidates"]] for k, v in a.items()})
        if ids.merkle_root_array(view.cand) != p["root"]:
            raise RegistryError("frozen registry root does not reproduce")
        return view

    def level_counts(self) -> dict:
        lv = {"family": 0, "hypothesis": 0, "strategy_spec": 0}
        for r in self.records.values():
            if r["level"] in lv:
                lv[r["level"]] += 1
        a = self._arrays()
        return {"families": lv["family"], "hypotheses": lv["hypothesis"], "strategy_specs": lv["strategy_spec"],
                "variants": int(np.unique(a["variant"], axis=0).shape[0]) if a["variant"].size else 0,
                "candidates": int(a["spec_index"].size)}


class FrozenView:
    """A frozen registry version in canonical order: canonical index i -> candidate."""

    def __init__(self, reg: Registry, payload: dict, order: np.ndarray, arrays: dict):
        self.reg = reg
        self.payload = payload
        self.root = payload["root"]
        self.order = order
        self.spec_index = arrays["spec_index"][order]
        self.grid_index = arrays["grid_index"][order]
        self.cand = arrays["cand"][order]
        self.variant = arrays["variant"][order]

    def __len__(self) -> int:
        return int(self.order.size)

    def candidate_hash(self, i: int) -> str:
        return bytes(self.cand[i]).hex()

    def candidate_id(self, i: int) -> str:
        return ids.short_id("candidate", self.candidate_hash(i))

    def describe(self, i: int) -> dict:
        spec = self.reg.spec(int(self.spec_index[i]))
        params, cost, sizing = point(spec, int(self.grid_index[i]))
        hyp = self.reg.records[spec["hypothesis"]]
        return {"template": spec["template"], "domain": hyp["domain"], "params": params, "cost_model": cost,
                "sizing": sizing, "spec_hash": self.reg.spec_hashes[int(self.spec_index[i])],
                "hypothesis_hash": spec["hypothesis"], "family_hash": hyp["family"]}

    def canonical_config(self, i: int) -> dict:
        """The candidate's canonical serialised configuration; its full hash is the candidate's identity."""
        spec = self.reg.spec(int(self.spec_index[i]))
        params, cost, sizing = point(spec, int(self.grid_index[i]))
        vh = ids.full_hash(variant_record(self.reg.spec_hashes[int(self.spec_index[i])], params))
        return candidate_record(vh, cost, sizing)

    def family_of_spec(self) -> tuple[np.ndarray, list]:
        """Per spec index: an integer family number (by sorted family hash)."""
        fams = sorted({self.reg.records[self.reg.records[h]["hypothesis"]]["family"]
                       for h in self.reg.spec_hashes})
        fnum = {f: i for i, f in enumerate(fams)}
        return np.array([fnum[self.reg.records[self.reg.records[h]["hypothesis"]]["family"]]
                         for h in self.reg.spec_hashes], dtype=np.int32), fams

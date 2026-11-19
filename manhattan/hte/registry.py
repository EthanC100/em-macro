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
from .log import AttemptLog, locked, recover_torn_tail


class RegistryError(RuntimeError):
    pass


# -- record builders -----------------------------------------------------------------------------------------

def family(name: str, mechanism: str, sign: str, density: str) -> dict:
    return {"level": "family", "name": name, "mechanism": mechanism, "sign": sign, "density": density,
            "synthetic": True}


def hypothesis(fam: dict, domain: str, frequency: str = "daily") -> dict:
    return {"level": "hypothesis", "family": ids.full_hash(fam), "domain": domain, "frequency": frequency,
            "synthetic": True}


def _order_key(v):
    return (0, float(v), "") if isinstance(v, (int, float)) and not isinstance(v, bool) else (1, 0.0, str(v))


def strategy_spec(hyp: dict, template: str, grid: dict, *, cost_models=("c1",), sizings=("unit_risk",)) -> dict:
    """A strategy spec in canonical form: every grid axis and binding list sorted, so that the same grid written
    in another order is the *same* spec (and a re-submission is a duplicate, not new candidates). There is no
    free-text label: anything that is not identity would create distinct specs with identical economics."""
    t = TP.TEMPLATES[template]
    return {"level": "strategy_spec", "hypothesis": ids.full_hash(hyp), "template": template,
            "template_version": t.version,
            "grid": {k: sorted(grid[k], key=_order_key) for k in sorted(grid)},
            "bindings": {"cost_model": sorted(cost_models), "sizing": sorted(sizings)}}


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
        if lvl != "strategy_spec":
            extra = set(rec) - set(req) - {"level", "synthetic"}
            if extra:
                probs.append(f"{lvl}: fields {sorted(extra)} are not part of the schema")
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
        elif len(set(canon)) != len(canon) or len({_order_key(v) for v in vals}) != len(vals):
            probs.append(f"grid.{k}: duplicate values (would register duplicate candidates)")
        elif vals != sorted(vals, key=_order_key):
            probs.append(f"grid.{k}: values must be in canonical (ascending) order; use registry.strategy_spec")
    for k, allowed in (("cost_model", tuple(TP.COST_MODELS)), ("sizing", TP.SIZINGS)):
        vals = bind.get(k) if isinstance(bind, dict) else None
        if not vals or any(v not in allowed for v in vals) or len(set(vals)) != len(vals):
            probs.append(f"bindings.{k} must be distinct values from {allowed}")
        elif list(vals) != sorted(vals):
            probs.append(f"bindings.{k} must be sorted; use registry.strategy_spec")
    extra = set(s) - {"level", "hypothesis", "template", "template_version", "grid", "bindings"}
    if extra:
        probs.append(f"strategy_spec: fields {sorted(extra)} are not part of the schema (non-identity text is "
                     "refused: it would make identical economics look like distinct specs)")
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

    def _reload(self) -> None:
        """Re-read everything from the log (called under the lock before any write: another writer may have
        registered or frozen since this object was built)."""
        recover_torn_tail(self.log.path)
        self.log.refresh()
        self.records, self.spec_hashes, self.segments = {}, [], []
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
                              "cand": np.zeros((0, 32), np.uint8), "variant": np.zeros((0, 32), np.uint8),
                              "semantic": np.zeros((0, 32), np.uint8)}
        return self._cand

    def __len__(self) -> int:
        return int(sum(s["n_candidates"] for s in self.segments))

    def spec(self, i: int) -> dict:
        return self.records[self.spec_hashes[i]]

    # -- submission --------------------------------------------------------------------------------------
    def submit(self, bundles: list[Bundle], *, probe_panel=None, allow_test_templates: bool = False) -> dict:
        """Validate and register under the workspace lock. Returns counts; every outcome is logged.

        ``probe_panel`` adds a second PIT probe on that panel; it never replaces the canonical probe.
        ``allow_test_templates`` must be passed explicitly to register a template marked ``test_only``; the
        allowance is recorded in the segment, and every package of such a family says so."""
        with locked(self.log.path):
            self._reload()
            return self._submit(bundles, probe_panel, allow_test_templates)

    def _probe_ok(self, template: str, version: int, code: str, panel, probed: dict) -> bool:
        ph = panel.data_hash if panel is not None else pit.canonical_panel_hash()
        key = (template, version, code, ph)
        if key not in probed:
            res = pit.probe(template, panel=panel)
            self.log.append("pit_probe", {"template": template, "version": version, "code": code, **res})
            probed[key] = res["passed"]
        return probed[key]

    def _submit(self, bundles: list[Bundle], probe_panel, allow_test_templates: bool = False) -> dict:
        report = {"submitted": len(bundles), "registered_specs": 0, "registered_candidates": 0,
                  "duplicate_submissions": 0, "rejected": 0}
        known_specs = set(self.spec_hashes)
        new_records, new_specs, seg_parts = [], [], []
        batch_specs: set[str] = set()
        code = pit.code_hash()
        # a probe result is reused only for the same template version, template and feature code, and probe panel;
        # a result without full coverage or without a recorded panel never counts as a pass
        probed = {}
        for r in self.log.of_type("pit_probe"):
            q = r["payload"]
            key = (q["template"], q["version"], q.get("code"), q.get("probe_panel"))
            probed[key] = bool(q["passed"] and q.get("probe_panel") and q.get("checks", 0) > 0
                               and q.get("checks") == q.get("expected_checks"))
        test_used = False
        for b in bundles:
            probs = validate_bundle(b)
            sh = None
            if not probs:
                sh = ids.full_hash(b.spec)
                tmpl, ver = b.spec["template"], b.spec["template_version"]
                if TP.TEMPLATES[tmpl].test_only and not allow_test_templates:
                    probs.append(f"template {tmpl!r} is test-only (pass allow_test_templates=True in tests)")
                elif not (self._probe_ok(tmpl, ver, code, None, probed) and
                          (probe_panel is None or self._probe_ok(tmpl, ver, code, probe_panel, probed))):
                    probs.append("template failed the PIT probe (positions depend on future data, or the probe "
                                 "did not reach full coverage)")
                elif TP.TEMPLATES[tmpl].test_only:
                    test_used = True
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
            seg_parts.append(self._enumerate(b.spec, sh, spec_index, b.hypothesis))
            report["registered_specs"] += 1
        if new_specs:
            arrays = {k: np.concatenate([p[k] for p in seg_parts]) for k in seg_parts[0]}
            report["registered_candidates"] = int(arrays["spec_index"].size)
            self._commit_segment(new_records, new_specs, arrays, test_templates=test_used)
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

    def _enumerate(self, spec: dict, sh: str, spec_index: int, hyp: dict) -> dict:
        domain, frequency = hyp["domain"], hyp["frequency"]
        keys = sorted(spec["grid"])
        b = spec["bindings"]
        n = grid_size(spec)
        cand = np.empty((n, 32), np.uint8)
        var = np.empty((n, 32), np.uint8)
        sem = np.empty((n, 32), np.uint8)
        i = 0
        for vals in itertools.product(*(spec["grid"][k] for k in keys)):
            params = dict(zip(keys, vals))
            vh = ids.full_hash(variant_record(sh, params))
            vb = np.frombuffer(bytes.fromhex(vh), np.uint8)
            for c in b["cost_model"]:
                for s in b["sizing"]:
                    cand[i] = np.frombuffer(bytes.fromhex(ids.full_hash(candidate_record(vh, c, s))), np.uint8)
                    var[i] = vb
                    # the economics alone (no family, hypothesis or spec text): equal across overlapping specs and
                    # across families that re-register the same rule under another name
                    sem[i] = np.frombuffer(bytes.fromhex(ids.full_hash(
                        {"domain": domain, "frequency": frequency, "template": spec["template"],
                         "template_version": spec["template_version"], "params": params, "cost_model": c,
                         "sizing": s})), np.uint8)
                    i += 1
        return {"spec_index": np.full(n, spec_index, np.int32), "grid_index": np.arange(n, dtype=np.int64),
                "cand": cand, "variant": var, "semantic": sem}

    def _commit_segment(self, new_records, new_specs, arrays, test_templates: bool = False) -> None:
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
        allsem = np.concatenate([self._arrays()["semantic"], arrays["semantic"]])
        sem_dups = int(allsem.shape[0] - np.unique(allsem, axis=0).shape[0]) if allsem.size else 0
        payload = {"segment": k, "file": fname, "sha256": sha, "records_file": rname, "records_sha256": rsha,
                   "test_templates": bool(test_templates),
                   "n_candidates": int(arrays["spec_index"].size),
                   "semantic_duplicates_total": sem_dups,
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
        """Fix the canonical order of every registered candidate and log its root, under the workspace lock.
        Idempotent: freezing an unchanged registry returns the existing version."""
        with locked(self.log.path):
            self._reload()
            return self._freeze()

    def _freeze(self) -> dict:
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

    def frozen(self, version: int | None = None, *, root: str | None = None) -> "FrozenView":
        """A frozen version: the latest, a version number, or the version with a given root (a run is bound to
        the root in its identity, never to "the latest")."""
        fr = self.log.of_type("registry_frozen")
        if not fr:
            raise RegistryError("registry has not been frozen")
        if root is not None:
            match = [r for r in fr if r["payload"]["root"] == root]
            if not match:
                raise RegistryError(f"no frozen version has root {root[:16]}")
            p = match[0]["payload"]
        else:
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
        sem = a["semantic"]
        return {"families": lv["family"], "hypotheses": lv["hypothesis"], "strategy_specs": lv["strategy_spec"],
                "variants": int(np.unique(a["variant"], axis=0).shape[0]) if a["variant"].size else 0,
                "candidates": int(a["spec_index"].size),
                # candidates whose economics (domain, template, parameters, binding) repeat another candidate's,
                # in an overlapping spec or under another family: still registered and counted, flagged here
                "semantic_duplicates": int(sem.shape[0] - np.unique(sem, axis=0).shape[0]) if sem.size else 0}


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
        self.semantic = arrays["semantic"][order]

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
        """Per global spec index: an integer family number (by sorted family hash), over the families of *this
        frozen view only* (a spec registered later cannot renumber the families of a run). Specs outside the
        view map to -1."""
        in_view = sorted({int(s) for s in np.unique(self.spec_index)})
        fam_of = {s: self.reg.records[self.reg.records[self.reg.spec_hashes[s]]["hypothesis"]]["family"]
                  for s in in_view}
        fams = sorted(set(fam_of.values()))
        fnum = {f: i for i, f in enumerate(fams)}
        out = np.full(len(self.reg.spec_hashes), -1, dtype=np.int32)
        for s, f in fam_of.items():
            out[s] = fnum[f]
        return out, fams

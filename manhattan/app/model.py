"""The view model of the operations app: frozen batches plus the private ledger, without any outcome.

``build_view(batches_dir, ledger)`` is a pure function of what it reads (and of an optional ``generated_utc``): it
returns a dict holding only operational facts, built from an **allow-list**:

* from the frozen batch folders (``runner.load_batch``): the family, hypothesis, variant and executable specs, the
  manifest's hashes and counts. ``ops_manifest.json`` and ``PR_BODY.md`` are not read: their variant report holds
  an effective variant count and power figures computed from exploration (screening) returns.
* from the private ledger: each record is first reduced by ``project`` to the fields listed in ``ALLOWED`` for its
  type. Nothing else of a record reaches the model. ``project`` refuses a float, or a string that spells a decimal,
  in any allowed field, so a schema change upstream fails closed instead of leaking.

``assert_no_outcomes(view)`` then walks the result and refuses any key on the deny-list (net, gross, return, pnl,
sharpe, turnover, exposure, rank, score, screening summaries...) and any float, or decimal-looking string, outside
the explicitly allowed parameter contexts (a spec's grid, a variant's point, a grid justification's mechanism range,
a signal's fixed parameters). ``build_view`` calls it before returning.

Ordering is by identifiers (batch, family id, hypothesis id, executable id): never by anything measured.

Counting levels are kept apart, as in BINDING_ACCOUNTING.md section 2: families, hypotheses, variants, unique
executable configurations (distinct executable spec hashes), registered predictions, and attempts (registered
executions: each retry is one more). No denominator for multiple testing is implied (D-1).
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from manhattan import spec as S
from manhattan.ops import data as D
from manhattan.ops import forward as FW
from manhattan.ops import promotion
from manhattan.ops import runner as R
from manhattan.ops import store as ST

SCHEMA = "manhattan.app.view/1"


class OutcomeLeak(ValueError):
    """Something that is or may be an outcome was about to enter the view model."""


# ---------------------------------------------------------------- the allow-list of ledger fields

# Per record type: the payload fields (dotted paths) the app may read. Types not listed are counted only.
ALLOWED: dict[str, tuple[str, ...]] = {
    "registration": ("prediction", "batch", "executable", "hypothesis", "family", "spec_hash", "manifest_hash",
                     "domain", "universe", "channel", "calendar", "registration_status", "registration_utc",
                     "eligible", "ineligible_reasons", "first_observation", "first_eligible_observation",
                     "declared_first_observation", "first_window_end", "horizon_sessions",
                     "sources.github_merged_at", "sources.merge_commit", "sources.witness.kind",
                     "sources.witness.attested_utc", "sources.witness.verified"),
    # an observation's values (net, gross, cost, exposure, turnover) are never read: only that it exists
    "observation": ("prediction", "executable", "date", "eligible", "reconstructed", "registration_status", "role"),
    "missed_observation": ("prediction", "date", "reason"),
    "capture": ("source", "first_period", "last_period", "rows"),
    "capture_failed": ("source", "asof"),
    "heartbeat": ("asof",),
    "missed_run": ("date",),
    "lock": ("expires_utc",),
    "lock_broken": ("expired_utc",),
    "unlock": (),
    "attempt_started": ("kind", "retry_of", "identity.spec_hash", "identity.executable", "identity.role",
                        "identity.batch", "subject.prediction", "subject.asof"),
    "attempt_completed": ("attempt_id", "status", "reason", "data_read"),
    "attempt_failed": ("attempt_id", "status", "reason", "data_read"),
    "attempt_aborted": ("attempt_id", "status", "reason", "data_read"),
    # a screening record's summary (mean, vol, sharpe, turnover, cost) and result hash are never read
    "screening": ("executable", "hypothesis", "role"),
    "accounting_epoch": (),
}
# Record-level fields every projection may carry (provenance identifies the run, never a value).
RECORD_FIELDS = ("type", "seq", "ts_utc", "provenance.run_id", "provenance.run_attempt", "provenance.source",
                 "provenance.retrieved_utc")
TERMINALS = {"attempt_completed": "completed", "attempt_failed": "failed", "attempt_aborted": "aborted"}

_DECIMAL = re.compile(r"^[-+]?(?:\d+\.\d*|\.\d+|\d+(?=[eE]))(?:[eE][-+]?\d+)?$")


def _get(obj, dotted: str):
    for part in dotted.split("."):
        if not isinstance(obj, dict) or part not in obj:
            return None
        obj = obj[part]
    return obj


def _safe_scalar(v, where: str):
    """Only str (not spelling a decimal), int, bool, None, or a list of those, may pass a projection."""
    if isinstance(v, float):
        raise OutcomeLeak(f"{where}: a float in an allowed ledger field")
    if isinstance(v, str) and _DECIMAL.match(v.strip()):
        raise OutcomeLeak(f"{where}: a decimal number in an allowed ledger field")
    if isinstance(v, list):
        return [_safe_scalar(x, where) for x in v]
    if isinstance(v, dict):
        raise OutcomeLeak(f"{where}: a mapping where a scalar was expected")
    if v is None or isinstance(v, (str, int, bool)):
        return v
    raise OutcomeLeak(f"{where}: a value of type {type(v).__name__}")


def project(record: dict) -> dict:
    """The allowed fields of one ledger record (flat, dotted keys), plus its idempotency key for attempt and lock
    records (attempt id, run id and attempt). Raises ``OutcomeLeak`` on an unexpected kind of value."""
    t = record.get("type")
    out = {}
    for f in RECORD_FIELDS:
        v = _get(record, f)
        if v is not None:
            out[f] = _safe_scalar(v, f"{t}.{f}")
    payload = record.get("payload") or {}
    for f in ALLOWED.get(t, ()):
        v = _get(payload, f)
        out[f] = _safe_scalar(v, f"{t}.payload.{f}")
    if t in ("attempt_started", "lock", "unlock", "lock_broken"):
        out["key"] = _safe_scalar(list(record.get("key") or []), f"{t}.key")
    return out


# ---------------------------------------------------------------- reading a ledger without writing it

class ReadOnlyLedger:
    """A private-ledger clone on disk, read without git and never written: ``chain.jsonl`` (hash chain verified on
    load) and ``journal.jsonl``. Offers the reading half of ``ops.store.Store``."""

    def __init__(self, workdir: Path):
        self.workdir = Path(workdir)
        self._records = ST.read_lines(self.workdir / ST.CHAIN)
        errs = ST.verify_chain(self._records)
        if errs:
            raise ST.StoreError("the private ledger does not verify: " + "; ".join(errs))

    @property
    def records(self) -> list[dict]:
        return list(self._records)

    @property
    def head(self) -> str:
        return self._records[-1]["hash"] if self._records else ST.GENESIS

    def of_type(self, type_: str) -> list[dict]:
        return [r for r in self._records if r["type"] == type_]

    def journal(self) -> list[dict]:
        return ST.read_lines(self.workdir / ST.JOURNAL)

    def unfinished(self) -> list[dict]:
        return ST.Store.unfinished(self)                 # the Store's own rule over this journal


# ---------------------------------------------------------------- evidence labels

# Activation gates (BINDING_ACCOUNTING.md sections 18-19). None is lifted; v1 shows them, it cannot lift them.
GATES = (
    ("G-1", "reconstructed provenance bound to the Store's capture records, independently verified"),
    ("G-2", "independent custody of anchors (D-7)"),
    ("G-3", "production engine callers register with the verified configuration"),
    ("G-4", "a workflow adopts the candidate lock (owner)"),
    ("G-5", "reserve stays disabled; no reserve workflow authorized"),
    ("G-6", "D-1: the counting unit of any multiple-testing denominator"),
    ("B-1", "every forward attempt's configuration claim re-verifies (F1)"),
    ("B-2", "one computation of the registered specification is the only path to a result (F2)"),
    ("B-3", "provenance and the observation set re-derive under independent review (G-1)"),
)
NOT_ELIGIBLE_GATES = "not eligible: activation gates closed"


def evidence_label(protocol_hash: str | None, config: dict | None, registration: dict | None = None) -> dict:
    """The only evidence label the app may show for a prediction, and why.

    Promotion (``manhattan.ops.promotion.status``) is the switch: until a validated protocol is adopted **and**
    ``claims.enabled`` is true, every prediction is ``not eligible: activation gates closed``. Even when it is
    switched on, the app does not classify anything itself: an ineligible registration keeps its recorded reasons
    (``manhattan.ops.timing``), and an eligible one shows the evidence classifier's lowest eligibility value
    (``manhattan.evidence.E_NONE``), with the classifier's provenance ``unverified`` (the app verifies nothing),
    because no classification is wired into the ledger yet (EVIDENCE_CLASSIFICATION.md, activation blockers)."""
    enabled, reason = promotion.status(protocol_hash, config)
    if not enabled:
        return {"label": NOT_ELIGIBLE_GATES, "eligible_for_evidence": False, "reason": reason}
    from manhattan import evidence as EVC
    if registration is not None and not registration.get("eligible"):
        reasons = ",".join(registration.get("ineligible_reasons") or []) or "ineligible"
        return {"label": f"not eligible: {reasons}", "eligible_for_evidence": False, "reason": "registration"}
    # the app verifies nothing itself, so its provenance is the classifier's ``unverified`` in every case
    return {"label": f"eligibility: {EVC.E_NONE} ({EVC.UNVERIFIED})", "eligible_for_evidence": False,
            "reason": "no_classification_wired"}


# ---------------------------------------------------------------- the no-outcome check

DENY_KEYS = frozenset({
    "net", "gross", "return", "returns", "ret", "pnl", "sharpe", "turnover", "exposure", "exposures", "rank",
    "ranking", "ranks", "score", "scores", "hit_rate", "summary", "mean_annual", "vol_annual", "cost_annual",
    "turnover_annual", "result_hash", "wealth", "drawdown", "max_drawdown", "volatility", "vol", "alpha", "beta",
    "t_stat", "tstat", "p_value", "pvalue", "power", "power_loss", "power_single", "power_search",
    "effective_variants", "m_eff", "variant_report", "screening_values", "screening_result", "performance",
    "profit", "loss", "cost", "sortino", "calmar", "information_ratio", "e_value", "evalue", "win_rate",
    "mean", "std", "values", "value", "weight_value", "net_exposure", "gross_exposure", "exposure_value",
})
DENY_TOKENS = frozenset({"net", "gross", "return", "returns", "pnl", "sharpe", "turnover", "rank", "ranking",
                         "ranked", "score", "drawdown", "wealth", "profit", "sortino", "calmar", "performance",
                         "hit", "outcome", "outcomes", "evalue", "pvalue"})
# Keys under which a spec's own parameters (decimal strings) may appear. Nothing measured lives there.
FLOAT_CONTEXTS = frozenset({"grid", "point", "parameters", "fixed_parameters", "mechanism_range"})
# Keys whose name contains a deny token but which hold no outcome (documentation of the policy itself).
KEY_EXCEPTIONS = frozenset({"outcomes_included"})


def _key_denied(k: str) -> bool:
    if k in KEY_EXCEPTIONS:
        return False
    lk = k.lower()
    if lk in DENY_KEYS:
        return True
    return any(t in DENY_TOKENS for t in re.split(r"[^a-z0-9]+", lk) if t)


def assert_no_outcomes(view) -> None:
    """Refuse a view holding a denied key, a float, or a decimal-looking string outside ``FLOAT_CONTEXTS``.
    The message names the path only, never the value."""
    errs: list[str] = []

    def walk(x, path: tuple, ctx: bool):
        if isinstance(x, dict):
            for k, v in x.items():
                if not isinstance(k, str):
                    errs.append("/".join(path) + ": a non-string key")
                    continue
                if _key_denied(k):
                    errs.append("/".join(path + (k,)) + ": a denied key")
                walk(v, path + (k,), ctx or k in FLOAT_CONTEXTS)
        elif isinstance(x, (list, tuple)):
            for i, v in enumerate(x):
                walk(v, path + (str(i),), ctx)
        elif isinstance(x, float):
            errs.append("/".join(path) + ": a float")                # never allowed, even in a parameter context
        elif isinstance(x, str):
            if not ctx and _DECIMAL.match(x.strip()):
                errs.append("/".join(path) + ": a decimal number outside a parameter context")
        elif not (x is None or isinstance(x, (bool, int))):
            errs.append("/".join(path) + f": a value of type {type(x).__name__}")

    walk(view, (), False)
    if errs:
        raise OutcomeLeak("refused: " + "; ".join(errs[:20]))


# ---------------------------------------------------------------- helpers over specs

def _params(x) -> object:
    """A spec parameter as the view holds it: ints and strings unchanged, floats as their canonical decimal."""
    if isinstance(x, float):
        return S._canon(x)
    if isinstance(x, dict):
        return {k: _params(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_params(v) for v in x]
    return x


def _is_synthetic_text(*texts) -> bool:
    return any("SYNTHETIC" in (t or "") for t in texts)


def _batches(batches_dir: Path):
    d = Path(batches_dir)
    for b in sorted(d.glob("AB-*")) if d.exists() else []:
        if b.is_dir() and re.fullmatch(r"AB-\d{4}", b.name):
            n = int(b.name[3:])
            manifest, specs = R.load_batch(d, n)
            yield n, manifest, specs


def _empty_attempts() -> dict:
    return {"registered": 0, "completed": 0, "failed": 0, "aborted": 0, "unfinished": 0, "retries": 0}


# ---------------------------------------------------------------- the ledger digest (projections only)

def _ledger_digest(ledger) -> dict:
    """Everything the model takes from the ledger, from projections only."""
    recs = [project(r) for r in ledger.records]
    by = defaultdict(list)
    for p in recs:
        by[p["type"]].append(p)
    regs = {}
    for p in by["registration"]:                              # the runner's rule: witnessed beats provisional
        if p["prediction"] not in regs or p["registration_status"] == "witnessed":
            regs[p["prediction"]] = p
    terminals = {}
    for t, status in TERMINALS.items():
        for p in by[t]:
            terminals[p["attempt_id"]] = status
    attempts = []                                             # (kind, prediction or None, spec hash, status, retry)
    for p in by["attempt_started"]:
        aid = p["key"][1] if len(p["key"]) > 1 else None
        attempts.append({"kind": p["kind"], "prediction": p["subject.prediction"],
                         "spec_hash": p["identity.spec_hash"], "status": terminals.get(aid, "unfinished"),
                         "retry": p["retry_of"] is not None})
    obs = defaultdict(lambda: {"recorded": 0, "reconstructed": 0, "dates": set()})
    for p in by["observation"]:
        o = obs[p["prediction"]]
        o["recorded"] += 1
        o["reconstructed"] += int(bool(p["reconstructed"]))
        o["dates"].add(p["date"])
    missed_obs = Counter(p["prediction"] for p in by["missed_observation"])
    caps = defaultdict(list)
    for p in by["capture"]:
        caps[p["source"]].append(p)
    cap_failed = Counter(p["source"] for p in by["capture_failed"])
    return {"by": by, "regs": regs, "attempts": attempts, "obs": obs, "missed_obs": missed_obs, "caps": caps,
            "cap_failed": cap_failed}


def _runner_status(ledger, dg: dict) -> dict:
    by = dg["by"]
    beats = sorted(p["asof"] for p in by["heartbeat"])

    def last(type_):
        if not by[type_]:
            return None
        p = by[type_][-1]
        k = p.get("key") or []
        return {"run_id": k[1] if len(k) > 1 else None, "run_attempt": k[2] if len(k) > 2 else None,
                "ts_utc": p.get("ts_utc")}

    ended = {tuple(p["key"][1:3]) for t in ("unlock", "lock_broken") for p in by[t]}
    active = [p for p in by["lock"] if tuple(p["key"][1:3]) not in ended]
    journal = ledger.journal()
    unfinished_attempts = sum(1 for a in dg["attempts"] if a["status"] == "unfinished")
    return {
        "last_heartbeat": beats[-1] if beats else None,
        "heartbeats": len(beats),
        "missed_runs": sorted(p["date"] for p in by["missed_run"]),
        "missed_runs_count": len(by["missed_run"]),
        "last_lock": last("lock"),
        "last_unlock": last("unlock"),
        "active_locks": len(active),
        "locks_broken": len(by["lock_broken"]),
        "journal": {"lines": len(journal), "entries": len({j["entry"] for j in journal}),
                    "unfinished_entries": len(ledger.unfinished())},
        "chain_ok": ST.verify_chain(ledger.records) == [],
        "ledger_records": len(ledger.records),
        "ledger_head": ledger.head,
        "unfinished_attempts": unfinished_attempts,
        "captures": len(by["capture"]),
        "capture_failures": len(by["capture_failed"]),
    }


# ---------------------------------------------------------------- the view

def build_view(batches_dir: Path, ledger=None, *, config: dict | None = None,
               generated_utc: str | None = None) -> dict:
    """The outcome-blind view model. ``ledger`` is an opened ``ops.store.Store`` or a ``ReadOnlyLedger`` (or None:
    batches only). ``config`` is ``config/manhattan.yaml`` as a dict (for the promotion switch); when omitted it is
    read from the repository."""
    if config is None:
        from manhattan import config as MC
        config = MC.load()
    dg = _ledger_digest(ledger) if ledger is not None else None
    regs = dg["regs"] if dg else {}
    asof = None
    runner = None
    if dg:
        runner = _runner_status(ledger, dg)
        asof = runner["last_heartbeat"]
    synthetic = False
    batches, all_families, all_hyps, all_variants, exe_hashes = [], 0, 0, 0, set()
    preds_seen: set = set()
    for n, manifest, specs in _batches(batches_dir):
        mh = S.spec_hash(manifest)
        bid = f"AB-{n:04d}"
        exes = sorted(R.batch_executables(specs), key=lambda x: x.id)
        code_versions = sorted({x.executable.get("code_version") for x in exes if x.executable.get("code_version")})
        freeze = {"batch_id": bid, "manifest_hash": mh, "merkle_root": manifest.get("merkle_root"),
                  "template_hash": manifest.get("template_hash"), "protocol_hash": manifest.get("protocol"),
                  "generator_model": manifest.get("generator_model"), "channel": manifest.get("channel", "blind"),
                  "code_versions": code_versions, "spec_count": len(manifest.get("spec_hashes", [])),
                  "critic_records": len(manifest.get("critic_records", []))}
        fams = sorted((sp for sp in specs.values() if sp["level"] == "family"), key=S.spec_id)
        hyps_by_fam = defaultdict(list)
        for sp in specs.values():
            if sp["level"] == "hypothesis":
                hyps_by_fam[sp["family"]].append(sp)
        exes_by_hyp = defaultdict(list)
        for x in exes:
            exes_by_hyp[S.spec_hash(x.hypothesis)].append(x)
        fam_views = []
        for fam in fams:
            fh = S.spec_hash(fam)
            fid = S.spec_id(fam)
            explanation = {("predicted_sign" if k == "sign" else k): v for k, v in sorted(fam.items()) if k != "level"}
            hyps = sorted(hyps_by_fam[fh], key=S.spec_id)
            synthetic = synthetic or _is_synthetic_text(fam.get("mechanism"))
            hyp_views, variants, preds, sources, calendars = [], [], [], {}, set()
            for h in hyps:
                hh = S.spec_hash(h)
                sig = h.get("signal") or {}
                hyp_views.append({
                    "id": S.spec_id(h), "spec_hash": hh, "domain": h.get("domain"), "frequency": h.get("frequency"),
                    "signal": {"kind": sig.get("kind"), "description": sig.get("description"),
                               "fixed_parameters": _params({k: v for k, v in sig.items()
                                                            if k not in ("kind", "description")})},
                    "grid": _params(h.get("grid") or {}),
                    "grid_justification": {p: {"reason": j.get("reason"),
                                               "mechanism_range": _params(j.get("mechanism_range"))}
                                           for p, j in sorted((h.get("grid_justification") or {}).items())},
                    "primary_binding": dict(h.get("primary_binding") or {}),
                    "timing": _params(h.get("timing") or {}),
                    "variants": len(exes_by_hyp[hh]),
                })
                if (h.get("timing") or {}).get("calendar"):
                    calendars.add(h["timing"]["calendar"])
                for ds in h.get("data_sources") or []:
                    av = ds.get("availability") or {}
                    sources[ds.get("name")] = {"name": ds.get("name"), "frequency": ds.get("frequency"),
                                               "period_label": ds.get("period_label"),
                                               "publication_lag_days": ds.get("publication_lag_days"),
                                               "availability_kind": av.get("kind"),
                                               "availability_reference": av.get("reference")}
                for x in exes_by_hyp[hh]:
                    pred = R.prediction_id(mh, x.spec_hash)
                    exe_hashes.add(x.spec_hash)
                    variants.append({"executable": x.id, "spec_hash": x.spec_hash, "variant": S.spec_id(x.variant),
                                     "hypothesis": S.spec_id(h), "parameters": _params(x.variant.get("point") or {}),
                                     "universe": x.universe.id, "domain": x.universe.domain,
                                     "calendar": x.universe.calendar,
                                     "cost_model_id": x.executable.get("cost_model_id"),
                                     "sizing_id": x.executable.get("sizing_id"),
                                     "code_version": x.executable.get("code_version"),
                                     "channel": x.variant.get("channel", manifest.get("channel", "blind")),
                                     "prediction": pred})
                    calendars.add(x.universe.calendar)
                    synthetic = synthetic or "synthetic" in x.universe.sources
                    preds.append((pred, x))
            # universe sources (the runner's capture registry) and their capture counts
            capture_sources = []
            for sid in sorted({s for _, x in preds for s in x.universe.sources}):
                src = D.SOURCES.get(sid)
                row = {"id": sid, "kind": src.kind if src else None, "calendar": src.calendar if src else None,
                       "publication_lag_days": src.lag_days if src else None,
                       "grace_days": src.grace_days if src else None,
                       "reference": src.source_reference if src else None}
                if dg is not None:
                    caps = dg["caps"].get(sid, [])
                    retrieved = sorted(c["provenance.retrieved_utc"][:10] for c in caps
                                       if c.get("provenance.retrieved_utc"))
                    row.update(captures=len(caps), first_capture=retrieved[0] if retrieved else None,
                               last_capture=retrieved[-1] if retrieved else None,
                               capture_failures=dg["cap_failed"].get(sid, 0))
                capture_sources.append(row)
                synthetic = synthetic or (src is not None and src.kind == "synthetic")
            pred_views, fam_attempts, fam_cov = [], defaultdict(_empty_attempts), Counter()
            reg_status = Counter()
            for pred, x in sorted(preds, key=lambda t: t[1].id):
                preds_seen.add(pred)
                reg = regs.get(pred)
                pv = {"prediction": pred, "executable": x.id, "spec_hash": x.spec_hash}
                if reg is None:
                    pv["registration"] = {"status": "unregistered"}
                    reg_status["unregistered"] += 1
                else:
                    pv["registration"] = {
                        "status": reg["registration_status"], "eligible": bool(reg["eligible"]),
                        "ineligible_reasons": reg["ineligible_reasons"] or [],
                        "registration_utc": reg["registration_utc"], "first_observation": reg["first_observation"],
                        "first_eligible_observation": reg["first_eligible_observation"],
                        "declared_first_observation": reg["declared_first_observation"],
                        "merged_utc": reg["sources.github_merged_at"], "merge_commit": reg["sources.merge_commit"],
                        "witness": reg["sources.witness.kind"], "witness_verified": reg["sources.witness.verified"],
                        "channel": reg["channel"]}
                    reg_status[reg["registration_status"]] += 1
                    reg_status["eligible" if reg["eligible"] else "ineligible"] += 1
                pv["evidence"] = evidence_label(manifest.get("protocol"), config, reg)
                if dg is not None:
                    att = defaultdict(_empty_attempts)
                    for a in dg["attempts"]:
                        if a["prediction"] == pred or (a["prediction"] is None and a["spec_hash"] == x.spec_hash):
                            c = att[a["kind"]]
                            c["registered"] += 1
                            c[a["status"]] += 1
                            c["retries"] += int(a["retry"])
                    pv["attempts"] = {k: dict(v) for k, v in sorted(att.items())}
                    for k, v in att.items():
                        for kk, vv in v.items():
                            fam_attempts[k][kk] += vv
                    o = dg["obs"].get(pred, {"recorded": 0, "reconstructed": 0})
                    missed = dg["missed_obs"].get(pred, 0)
                    expected = 0
                    if reg is not None and asof is not None:
                        fo = date.fromisoformat(reg["first_observation"])
                        a_ = date.fromisoformat(asof)
                        expected = len(FW.sessions(x.universe, fo, a_)) if a_ > fo else 0
                    cov = {"asof": asof, "expected_days": expected, "recorded_days": o["recorded"],
                           "missed_observation_days": missed, "reconstructed_days": o["reconstructed"],
                           "pending_days": max(0, expected - o["recorded"] - missed)}
                    pv["coverage"] = cov
                    for k in ("expected_days", "recorded_days", "missed_observation_days", "reconstructed_days",
                              "pending_days"):
                        fam_cov[k] += cov[k]
                pred_views.append(pv)
            labels = sorted({p["evidence"]["label"] for p in pred_views})
            fam_views.append({
                "id": fid, "spec_hash": fh, "batch": bid, "anchor": f"fam-{fid}",
                "channel": manifest.get("channel", "blind"),
                "explanation": explanation,
                "hypotheses": hyp_views,
                "variants": variants,
                "freeze": freeze,
                "provenance": {"declared_sources": [sources[k] for k in sorted(sources, key=str)],
                               "capture_sources": capture_sources, "calendars": sorted(calendars)},
                "registration": dict(sorted(reg_status.items())),
                "evidence_labels": labels,
                "attempts": {k: dict(v) for k, v in sorted(fam_attempts.items())} if dg is not None else None,
                "coverage": dict(fam_cov) if dg is not None else None,
                "predictions": pred_views,
                "counts": {"hypotheses": len(hyps), "variants": len(variants),
                           "unique_executable_configurations": len({v["spec_hash"] for v in variants}),
                           "registered_predictions": sum(1 for p in pred_views
                                                         if p["registration"]["status"] != "unregistered")},
            })
            all_families += 1
            all_hyps += len(hyps)
            all_variants += len(variants)
        batches.append({**freeze, "declared_counts": dict(manifest.get("counts") or {}), "families": fam_views})
    counts = {"batches": len(batches), "families": all_families, "hypotheses": all_hyps, "variants": all_variants,
              "unique_executable_configurations": len(exe_hashes),
              "registered_predictions": sum(1 for p in preds_seen if p in regs)}
    if dg is not None:
        kinds = defaultdict(_empty_attempts)
        for a in dg["attempts"]:
            c = kinds[a["kind"]]
            c["registered"] += 1
            c[a["status"]] += 1
            c["retries"] += int(a["retry"])
        counts.update(
            registrations_in_ledger=len(regs),
            predictions_eligible=sum(1 for r in regs.values() if r["eligible"]),
            predictions_ineligible=sum(1 for r in regs.values() if not r["eligible"]),
            predictions_provisional=sum(1 for r in regs.values() if r["registration_status"] == "provisional"),
            attempts_total=len(dg["attempts"]),
            attempts_by_kind={k: dict(v) for k, v in sorted(kinds.items())},
            observation_records=sum(o["recorded"] for o in dg["obs"].values()),
            missed_observation_records=sum(dg["missed_obs"].values()),
            screening_records=len(dg["by"]["screening"]))
        synthetic = synthetic or any(s == "synthetic" for s in dg["caps"])
    some_protocol = next((b["protocol_hash"] for b in batches if b.get("protocol_hash")), None)
    ev = evidence_label(some_protocol, config)
    view = {
        "schema": SCHEMA,
        "generated_utc": generated_utc,
        "synthetic": synthetic,
        "ledger_connected": ledger is not None,
        "blinding": {"outcomes_included": False,
                     "policy": "operational facts only: no return, PnL, Sharpe, hit rate, exposure, turnover, "
                               "ranking or screening value, nor anything derived from them",
                     "order": "by identifier, never by anything measured"},
        "evidence": {**ev, "promotion": promotion.status(some_protocol, config)[1],
                     "gates": [{"id": g, "requirement": s, "state": "not lifted"} for g, s in GATES]},
        "counts": counts,
        "runner": runner,
        "batches": batches,
    }
    view = json.loads(json.dumps(view))                          # plain JSON types only (tuples become lists)
    assert_no_outcomes(view)
    return view

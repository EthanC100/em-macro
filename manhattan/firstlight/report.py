"""First Light harness report: built from the ledger plus the anchor only, deterministically.

Three files:

* ``report.json`` and ``report.md``: the census, the freeze, the data and code identity, and **every variant's
  result, negatives included** (exploration role, evidential weight 0, no claim). They hold outcomes.
* ``public_index.json``: the one artefact meant to be public. It carries no outcome key (``ledger.OUTCOME_KEYS``);
  ``scan_public`` checks it and the builder refuses to write one that fails.

Nothing in-memory from the run is used: the inputs are the ledger file and the anchors directory. The builder
refuses (fail closed) unless the ledger verifies against its anchors with no unanchored tail and the latest anchor
closes a run. Run-specific fields (record timestamps, record and head hashes, attempt IDs, anchor times) are left
out of the report so that two runs of the same code on the same seed give byte-identical reports; they stay in
the ledger and the anchors file.
"""
from __future__ import annotations

import json
from pathlib import Path

from manhattan import attempts
from manhattan import ledger as L
from manhattan.evidence import E_DESCRIPTIVE

from . import anchor_stub

SCHEMA, PUBLIC_SCHEMA = "firstlight.report/1", "firstlight.public_index/1"
REPORT_JSON, REPORT_MD, PUBLIC_JSON = "report.json", "report.md", "public_index.json"
HARNESS_KIND = "firstlight_synthetic_harness"
SUMMARY_FIELDS = ("n_obs", "mean_annual", "vol_annual", "sharpe", "turnover_annual", "cost_annual", "skipped_trades")
EXCLUDED = ("ts_utc", "record hashes", "ledger head", "attempt IDs", "ledger_id", "anchor utc", "ledger merkle_root")


class ReportRefused(RuntimeError):
    """The ledger and its anchors do not support a report (fail closed)."""


def dumps(obj) -> bytes:
    return (json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def scan_public(obj) -> list[str]:
    """Paths of outcome keys in a would-be public artefact (empty when it may be published)."""
    return L.outcome_keys_in(obj)


def _freeze_record(recs: list[dict]) -> dict:
    found = [r for r in recs if r["type"] == "batch_freeze" and isinstance(r["payload"], dict)
             and r["payload"].get("kind") == HARNESS_KIND]
    if len(found) != 1:
        raise ReportRefused("the ledger must hold exactly one harness batch_freeze record")
    return found[0]


def build(ledger_path: Path, anchors_dir: Path) -> dict:
    """The report as a dict (and, under ``"public"``, the public index), or ``ReportRefused``."""
    check = anchor_stub.verify_against_anchor(ledger_path, anchors_dir)
    if not check["ok"]:
        raise ReportRefused("the ledger does not verify against its anchors: " + "; ".join(check["problems"]))
    if check["latest_event"] != "run_close":
        raise ReportRefused("the latest anchor does not close a run: no report before run_close")
    snapshot = Path(ledger_path).read_bytes()
    recs, errs = L.verify_snapshot(snapshot)
    if errs:
        raise ReportRefused("; ".join(errs))
    latest = anchor_stub.read_anchors(anchor_stub.anchors_path(anchors_dir, anchor_stub.ledger_id(snapshot)))[-1][0]
    recon = attempts.reconcile(ledger_path=ledger_path,
                               ledger_anchor={"records": latest["records"], "head": latest["head"]})
    fz = _freeze_record(recs)
    fp = fz["payload"]
    if any(r["type"] == "evaluation_started" and r["seq"] < fz["seq"] for r in recs):
        raise ReportRefused("an evaluation was registered before the batch was frozen")

    starts = {r["hash"]: r["payload"] for r in recs if r["type"] == "evaluation_started"}
    by_exec: dict[str, dict] = {}
    for r in recs:
        p = r["payload"]
        if r["type"] in L.COMPLETIONS:
            by_exec.setdefault(p["executable"], {"completions": [], "terminals": []})["completions"].append(r)
        elif r["type"] in ("attempt_failed", "attempt_aborted"):
            ex = starts.get(p.get("attempt_id"), {}).get("executable")
            by_exec.setdefault(ex, {"completions": [], "terminals": []})["terminals"].append(r)
    variants, weights, data_hashes, versions = [], set(), set(), set()
    for v in fp["variants"]:
        seen = by_exec.get(v["executable"], {"completions": [], "terminals": []})
        row = {"variant": v["variant"], "executable": v["executable"], "point": v["point"]}
        if seen["completions"]:
            c = seen["completions"][0]
            p = c["payload"]
            weights.add(p["evidential_weight"])
            data_hashes.add(p["data_hash"])
            versions.add(json.dumps(p["code_version"], sort_keys=True))
            row.update(status="completed", record_type=c["type"], role=p["role"], result_hash=p["result_hash"],
                       evidential_weight=p["evidential_weight"],
                       summary={k: p["summary"].get(k) for k in SUMMARY_FIELDS})
        elif seen["terminals"]:
            row.update(status=seen["terminals"][-1]["type"].removeprefix("attempt_"), result_hash=None,
                       evidential_weight=0, summary=None)
        else:
            row.update(status="not_evaluated", result_hash=None, evidential_weight=0, summary=None)
        variants.append(row)
    done = [r for r in variants if r["status"] == "completed"]
    c = {k: recon[k] for k in ("registered_executions", "completed", "failed", "aborted", "unfinished",
                               "superseded_interrupted", "retries")}
    census = {**c,
              "balanced": c["registered_executions"] == c["completed"] + c["failed"] + c["aborted"]
              + c["superseded_interrupted"] + c["unfinished"],
              "identity": "registered = completed + failed + aborted + superseded_interrupted + unfinished",
              "violations": len(recon["violations"]), "access_reconciled": recon["access_reconciled"],
              "distinct_specifications": recon["distinct_specifications"],
              "completed_evaluation_keys": recon["completed_evaluation_keys"],
              "independent_statistical_tests": recon["independent_statistical_tests"],
              "independently_anchored": False}
    code = [json.loads(x) for x in sorted(versions)]
    summaries = [r["summary"] for r in done]
    report = {
        "schema": SCHEMA, "title": "First Light harness report (SYNTHETIC)", "synthetic": True, "claim": "none",
        "label": fp["label"],
        "data": fp["data"],
        "data_hash_in_every_completion": data_hashes == {fp["data"]["pit_data_hash"]} if done else False,
        "code": code[0] if len(code) == 1 else code,
        "freeze": fp["freeze"], "family": fp["family"], "hypothesis": fp["hypothesis"], "grid": fp["grid"],
        "window": fp["window"], "execution": fp["execution"],
        "census": census,
        "variants_in_grid": fp["grid_size"], "variants_evaluated": len({r["executable"] for r in done}),
        "evidence": {"role": "exploration", "class": "exploration", "eligibility": E_DESCRIPTIVE,
                     "evidential_weight": max(weights) if weights else 0},
        "anchor": {k: check[k] for k in ("ok", "anchors", "anchored_records", "latest_event",
                                         "independently_anchored", "custody")},
        "probes": ([r["payload"].get("probes") for r in recs if r["type"] == "run_summary"] or [None])[-1],
        "runs": sum(1 for r in recs if r["type"] == "run_summary"),
        "negative_sharpe_variants": sum(1 for s in summaries if s["sharpe"] is not None and float(s["sharpe"]) < 0),
        "variants": variants,
        "excluded_run_specific_fields": list(EXCLUDED),
    }
    public = {
        "schema": PUBLIC_SCHEMA, "synthetic": True, "claim": "none", "label": fp["label"],
        "data": {k: fp["data"][k] for k in ("synthetic", "real_data", "licensed", "generator", "seed",
                                            "file_sha256", "pit_data_hash", "start", "end")},
        "code": report["code"], "freeze": fp["freeze"], "census": census,
        "variants_in_grid": report["variants_in_grid"], "variants_evaluated": report["variants_evaluated"],
        "evidence": report["evidence"], "anchor": report["anchor"],
        "variants": [{k: r[k] for k in ("variant", "executable", "point", "status", "result_hash",
                                        "evidential_weight")} for r in variants],
    }
    bad = scan_public(public)
    if bad:
        raise ReportRefused("the public index would carry outcome keys: " + ", ".join(bad))
    report["public"] = public
    return report


def _num(x, nd: int = 4) -> str:
    """The ledger stores non-integer numbers as decimal strings (``spec.canonical_bytes``)."""
    if x is None:
        return "n/a"
    if isinstance(x, int):
        return str(x)
    return f"{float(x):.{nd}f}"


def markdown(rep: dict) -> str:
    c, d, fz = rep["census"], rep["data"], rep["freeze"]
    code = rep["code"] if isinstance(rep["code"], dict) else {"commit": "several", "engine_sha256": "several"}
    out = [f"# {rep['title']}", "",
           f"**{rep['label']}** Evidence class `{rep['evidence']['class']}` (`{rep['evidence']['eligibility']}`), "
           f"evidential weight {rep['evidence']['evidential_weight']}. No claim.", "",
           "## Identity", "",
           "| item | value |", "|---|---|",
           f"| data | synthetic: {d['synthetic']}; real data: {d['real_data']}; licensed: {d['licensed']}; "
           f"generator `{d['generator']}`, seed {d['seed']} |",
           f"| data file SHA-256 | `{d['file_sha256']}` |",
           f"| point-in-time data hash | `{d['pit_data_hash']}` (in every completion: "
           f"{rep['data_hash_in_every_completion']}) |",
           f"| span | {d['start']} to {d['end']}, {d['rows']} weekdays, series {', '.join(d['series'])} |",
           f"| code commit | `{code['commit']}` |",
           f"| engine SHA-256 | `{code['engine_sha256']}` |",
           f"| freeze | {fz['batch']}, manifest `{fz['manifest_hash']}`; {fz['kind']} |",
           f"| freeze verification | {fz['verification']} |",
           f"| window | {rep['window']['id']} ({rep['window']['role']}) |",
           f"| execution | lag {rep['execution']['lag']}, rebalance {rep['execution']['rebalance']}, cost model "
           f"`{rep['execution']['cost_model_id']}` ({rep['execution']['cost_one_way']} one way) |",
           "", "## Census", "",
           "| count | value |", "|---|---|"]
    for k in ("registered_executions", "completed", "failed", "aborted", "superseded_interrupted", "unfinished",
              "retries", "balanced", "violations", "access_reconciled", "independently_anchored"):
        out.append(f"| {k} | {c[k]} |")
    out += [f"| variants evaluated / grid size | {rep['variants_evaluated']} / {rep['variants_in_grid']} |",
            "", f"Identity: {c['identity']}. Anchor: ok {rep['anchor']['ok']}, {rep['anchor']['anchors']} anchor(s), "
            f"{rep['anchor']['anchored_records']} records, latest `{rep['anchor']['latest_event']}`; "
            f"{rep['anchor']['custody']}.", "",
            f"## Every variant ({rep['negative_sharpe_variants']} with a negative Sharpe ratio)", "",
            "| variant | point | status | Sharpe | mean (annual) | vol (annual) | cost (annual) | n | result hash |",
            "|---|---|---|---|---|---|---|---|---|"]
    for r in rep["variants"]:
        s = r["summary"] or {}
        pt = ", ".join(f"{k}={v}" for k, v in sorted(r["point"].items()))
        out.append(f"| {r['variant']} | {pt} | {r['status']} | {_num(s.get('sharpe'))} | "
                   f"{_num(s.get('mean_annual'))} | {_num(s.get('vol_annual'))} | {_num(s.get('cost_annual'), 5)} | "
                   f"{_num(s.get('n_obs'))} | `{(r['result_hash'] or 'none')[:16]}` |")
    out += ["", "Left out as run-specific (they are in the ledger and the anchors file): "
            + ", ".join(rep["excluded_run_specific_fields"]) + ".", ""]
    return "\n".join(out)


def write(ledger_path: Path, anchors_dir: Path, directory: Path) -> dict:
    """Build and write the three files; returns {name: bytes}."""
    rep = build(ledger_path, anchors_dir)
    public = rep.pop("public")
    files = {REPORT_JSON: dumps(rep), REPORT_MD: markdown(rep).encode("utf-8"), PUBLIC_JSON: dumps(public)}
    if scan_public(json.loads(files[PUBLIC_JSON])):
        raise ReportRefused("the public index carries an outcome key")
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (directory / name).write_bytes(data)
    return files

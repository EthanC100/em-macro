"""Development status of the simulation programme, read-only: what is on file, what may be counted, and what each
pre-registered criterion says about it so far.

    python -m manhattan.sim.dev_status [--out results/manhattan_sim] [--include-stale] [--md FILE] [--json FILE]

Nothing here runs a simulation, writes a replication record, touches the run log or decides anything. It reads the
record files under ``--out`` and sorts every run of the development plan (SIM_PREREG section 3.1 and SIM_PREREG_v2
section 3) and every criterion into separate categories, so that a development read is never mistaken for a
confirmation result or for a method selection:

- **runs**: complete at the pre-registered count for the code now checked out; incomplete; pilot only; or on file
  only for **other code** (records of different code are never pooled: SIM_PREREG_v2 section 9);
- **criteria**: per development scenario, the verdict of the existing metric code (``metrics``, ``metrics_v2``) on
  complete runs of the current code. A verdict is never computed on records of other code: with
  ``--include-stale`` their numbers are shown, and every verdict reads "not decided: other code";
- **screening candidates**: the development half of SIM_PREREG section 7 step 1 (V1 and V4 where required, V3 for
  candidate (i), V10(a), V11 for screening). The other half needs the held-out scenarios of a tagged confirmation
  run, so **no candidate is called eligible here and no method is selected**. The power numbers of step 2 are
  deliberately not computed;
- **components**: the forward test, the hierarchical model, tiers and dormancy (SIM_PREREG section 8.1 rule 2);
- **held-out**: H01-H12 are listed with whether their worlds are coded and whether any held-out run is on record.
  Nothing held-out is generated, run or read;
- **missing or unverified evidence**.

The output is deterministic for given record files (no clock, sorted keys, the bootstrap seeds of ``metrics``), and
carries the SHA-256 of every record file it read.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

from . import criteria as cr
from . import criteria_v2 as cr2
from . import hb_v2, metrics, metrics_v2, run, runlog, world

GROUP_DEVELOPMENT = "development"
HELD_OUT_V1 = world.HELD_OUT                      # SIM_PREREG section 3.2
HELD_OUT_V2 = cr2.HEDGED_HELD_OUT                 # SIM_PREREG_v2 section 3.2
HELD_OUT_SIZES = {                                # the "sizes" column of the two tables, as data
    "H01": ("STD", "STD E-ALL"), "H02a": ("STD",), "H02b": ("STD E-ALL",), "H02c": ("STD E-ALL",),
    "H03": ("STD", "HB"), "H04": ("STD", "STD E-ALL"), "H05": ("STD", "HB"), "H06": ("STD", "HB"), "H07": ("HB",),
    "H08m": ("STD E-ALL",), "H08x": ("STD E-ALL",), "H09": ("HB",), "H10": ("STD E-ALL", "HB"),
    "H11": ("STD", "LONG", "HB"), "H12": ("STD",)}
SCREENING = ("V1", "V4")                          # SIM_PREREG section 7 step 1, both candidates
CANDIDATE_NAME = {"i": "candidate (i)", "ii": "candidate (ii)"}
COMPONENTS = {                                    # SIM_PREREG section 8.1 rule 2, and SIM_PREREG_v2 section 5
    "within-family tests (SPA, Romano-Wolf, Benjamini-Bogomolov link)": ("V3", "V4"),
    "forward test (e-process, e-LOND)": ("V2", "V5", "V9", "V11 forward"),
    "hierarchical model: posterior-based tiers": ("V6", "V8", "V12"),
    "hierarchical model: dormancy": ("V7", "V12"),
}
CODE_PROPERTIES = {                               # SIM_PREREG_v2 section 5: properties of the code, tests in the suite
    "V10(a)": "results file v10a.json and tests/test_manhattan_sim_pipeline.py",
    "V13": "tests/test_manhattan_spa_hedged.py",
    "V14": "tests/test_manhattan_adaptive_weight.py",
    "V15": "tests/test_manhattan_tailrisk.py",
}


# ------------------------------------------------------------------------------------------------ reading records

def _read_all(path: Path) -> list[dict]:
    rows = []
    for p, opener in ((path, open), (path.with_suffix(".jsonl.gz"), gzip.open)):
        if p.exists():
            with opener(p, "rt", encoding="utf-8") as f:
                rows += [json.loads(line) for line in f if line.strip()]
    return rows


def _digest(path: Path) -> dict:
    out = {}
    for p in (path, path.with_suffix(".jsonl.gz")):
        if p.exists():
            out[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _one_per_rep(rows: list[dict]) -> list[dict]:
    seen = {}
    for r in rows:
        seen.setdefault(r["rep"], r)
    return [seen[k] for k in sorted(seen)]


def _gaps(have: set, need: int) -> str:
    left = [r for r in range(need) if r not in have]
    if not left:
        return "none"
    out, start = [], left[0]
    for a, b in zip(left, left[1:] + [None]):
        if b != a + 1:
            out.append(f"{start}" if start == a else f"{start} to {a}")
            start = b
    return ", ".join(out)


def inventory(out: Path) -> list[dict]:
    """One entry per run of the development plan under version 2: what is on file, by code, and its state."""
    entries = []
    for scenario, size in run.development_plan("v2"):
        version = run.route(scenario, size, "v2")
        path = run.reps_path(scenario, size, 0, out, version)
        rows = _read_all(path)
        need = cr2.replications(scenario, size)
        now = run.code_hash(size, version=version)
        hb = size == "HB" and version == "v2"
        usable = [r for r in rows if r.get("code") == now and (not hb or r.get("review_step") == hb_v2.REVIEW_STEP)]
        current = _one_per_rep([r for r in usable if isinstance(r.get("rep"), int) and 0 <= r["rep"] < need])
        by_code: dict = {}
        used = {id(r) for r in usable}
        for r in rows:
            if id(r) in used:
                continue
            key = (r.get("code"), r.get("review_step") if hb else None)
            by_code.setdefault(key, set()).add(r.get("rep"))
        others = [{"code": c, "review_step": s, "replications": len(reps)} for (c, s), reps in
                  sorted(by_code.items(), key=lambda kv: (-len(kv[1]), str(kv[0])))]
        n = len(current)
        stale_full = [o for o in others if o["replications"] >= need and (not hb or o["review_step"] == hb_v2.REVIEW_STEP)]
        if n >= need:
            state = "complete"
        elif n > 0:
            state = "incomplete"
        elif stale_full:
            state = "other code only"
        elif rows:
            state = "other code only (incomplete)"
        else:
            state = "nothing on file"
        entries.append({"scenario": scenario, "size": size, "group": GROUP_DEVELOPMENT, "code_route": version,
                        "kind": "hedged twin" if cr2.is_twin(scenario) else ("HB" if size == "HB" else
                                                                            ("D11" if version == "v2" else "v1")),
                        "current_code": now, "required": need, "on_file_current": n,
                        "missing_current": _gaps({r["rep"] for r in current}, need), "state": state,
                        "other_code": others, "files": _digest(path), "_current": current,
                        "_stale": _one_per_rep([r for r in rows if stale_full and r.get("code") == stale_full[0]["code"]
                                                and (not hb or r.get("review_step") == hb_v2.REVIEW_STEP)])
                        if stale_full and n < need else []})
    return entries


# ------------------------------------------------------------------------------------------------ verdicts

def classify(verdict: str) -> str:
    """The category of a verdict string written by ``metrics``: pass, FAIL, not decided, not evaluated, reported."""
    v = verdict or ""
    if v == "pass":
        return "pass"
    if v == "FAIL":
        return "FAIL"
    if v.startswith("not evaluated"):
        return "not evaluated (small group)"
    if v.startswith("pilot") or v.startswith("not decided"):
        return "not decided"
    if v == "no data":
        return "no data"
    return "reported"


def _rows(entry: dict, reps: list[dict]) -> list[metrics.Row]:
    scenario, size = entry["scenario"], entry["size"]
    if entry["kind"] == "hedged twin":
        return metrics_v2.summarise_spa(reps, scenario)
    if entry["kind"] == "D11":
        return metrics_v2.summarise_spa(reps, scenario) + metrics.summarise(reps, scenario, size)
    if entry["kind"] == "HB":
        return metrics_v2.summarise_hb(reps, scenario)
    return metrics.summarise(reps, scenario, size)


def _candidate(what: str) -> str | None:
    if "candidate (ii)" in what:
        return "ii"
    if "candidate (i)" in what:
        return "i"
    return None


def criterion_rows(entry: dict, include_stale: bool) -> list[dict]:
    """The criterion rows of one run, as dictionaries with a ``category``; empty when there is nothing to read."""
    if entry["state"] == "complete":
        reps, stale = entry["_current"], False
    elif include_stale and entry["_stale"]:
        reps, stale = entry["_stale"], True
    else:
        return []
    out = []
    for r in _rows(entry, reps):
        if not r.criterion:
            continue
        d = r.as_dict()
        if d["criterion"] == "V11" and "forward" in d["what"]:
            d["criterion"] = "V11 forward"
        if d["criterion"] == "V3" and entry["kind"] in ("D11", "hedged twin") and not d["what"].startswith(
                metrics_v2.NAME["v31"]):
            continue                                  # SIM_PREREG_v2 V3: in D11 and the twins only the hedge-aware test is judged
        d["candidate"] = _candidate(d["what"])
        d["replications"] = len(reps)
        d["category"] = classify(d["verdict"]) if d["required"] else "reported (not required here)"
        d["computed_on_other_code"] = None
        if stale:                                     # shown, never decided: records of other code are not pooled
            d["computed_on_other_code"] = d["verdict"]
            d["verdict"] = f"not decided: records of other code ({reps[0].get('code')})"
            d["category"] = "not decided"
        d["records_code"] = reps[0].get("code")
        out.append({k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in d.items()})
    return out


def _gate(rows: list[dict], criteria: tuple, candidate: str | None, runs: list[dict]) -> dict:
    """Pass only if every required row of these criteria passes and every run that requires them is complete."""
    cats = Counter()
    for r in rows:
        if r["criterion"] in criteria and r["required"] and (candidate is None or r["candidate"] in (None, candidate)):
            cats[r["category"]] += 1
    incomplete = [f"{e['scenario']} {e['size']}" for e in runs if e["state"] != "complete"
                  and any(cr_required(c, e["scenario"], e["size"]) for c in criteria)]
    if cats.get("FAIL"):
        state = "FAIL on development"
    elif incomplete or cats.get("not decided") or cats.get("no data"):
        state = "not decided"
    elif cats.get("pass"):
        state = "development rows pass"
    else:
        state = "no required row"
    return {"state": state, "rows": dict(sorted(cats.items())), "runs_not_complete": incomplete}


def cr_required(criterion: str, scenario: str, size: str) -> bool:
    base = criterion.split()[0]
    if cr2.is_twin(scenario):                     # SIM_PREREG_v2 section 5: a twin is judged on V3 only
        return base == "V3"
    if base in ("V3", "V5"):                      # M3 and M5 come from the screening pipeline: STD and LONG runs only
        if size == "HB":
            return False
        return scenario in (cr2.V3_REQUIRED if base == "V3" else cr.V5_REQUIRED)
    if base == "V12":
        return size == "HB"
    if base in ("V1", "V2", "V4", "V5", "V6", "V7", "V8", "V9", "V10", "V11"):
        return cr.required(base, scenario, size)
    return False


# ------------------------------------------------------------------------------------------------ held-out

def heldout_status(log: list[dict]) -> list[dict]:
    coded = set(world.SCENARIOS)
    out = []
    for h in HELD_OUT_V1 + HELD_OUT_V2:
        made = [r for r in log if r.get("scenario") == h and r.get("event") in ("start", "end")]
        refused = [r for r in log if r.get("scenario") == h and r.get("status") == "refused"]
        out.append({"scenario": h, "pre_registration": "v1" if h in HELD_OUT_V1 else "v2",
                    "sizes": list(HELD_OUT_SIZES[h]), "world_coded": h in coded, "runs_on_record": len(made),
                    "refusals_on_record": len(refused)})
    return out


# ------------------------------------------------------------------------------------------------ build

def build(out: Path, include_stale: bool = False) -> dict:
    out = Path(out)
    entries = inventory(out)
    log = runlog.read(out / "runs.jsonl")
    rows = []
    for e in entries:
        for r in criterion_rows(e, include_stale):
            rows.append({"scenario": e["scenario"], "size": e["size"], **r})
    v10 = out / "v10a.json"
    v10a = json.loads(v10.read_text(encoding="utf-8")) if v10.exists() else None
    if v10a:
        same = all(s.get("identical") for s in v10a.get("scenarios", {}).values())
        rows.append({"scenario": "D09a, D09b", "size": "STD", "metric": "V10(a)", "criterion": "V10",
                     "what": f"designated blind statistics identical with and without the adaptive channel "
                             f"({v10a.get('replications')} replications, {v10a.get('batches')} batches)",
                     "estimate": None, "lo": None, "hi": None, "required": True, "candidate": None,
                     "verdict": "pass" if same else "FAIL", "category": "pass" if same else "FAIL",
                     "threshold": "bit-for-bit identical", "replications": v10a.get("replications")})
    candidates = {}
    for cand in ("i", "ii"):
        crit = SCREENING + (("V3",) if cand == "i" else ()) + ("V10", "V11")
        g = _gate([r for r in rows if r["criterion"] != "V11 forward"], crit, cand, entries)
        g["criteria"] = list(crit)
        g["held_out_half"] = "not evaluated: needs a tagged confirmation run (SIM_PREREG section 8.1 rule 4)"
        g["eligible"] = "not determined"
        candidates[cand] = g
    components = {name: _gate(rows, crit, None, entries) for name, crit in COMPONENTS.items()}
    for name in components:
        components[name]["held_out_half"] = "not evaluated"
        components[name]["note"] = ("forward criteria must hold for the candidate that is selected (SIM_PREREG "
                                    "section 2.5); no candidate is selected, so rows of both are shown"
                                    if name.startswith("forward") else "")
    held = heldout_status(log)
    missing = []
    for e in entries:
        if e["state"] != "complete":
            others = "; ".join(f"{o['replications']} by code {o['code']}" + (f" (review step {o['review_step']})"
                                                                               if o["review_step"] is not None else "")
                               for o in e["other_code"]) or "none"
            missing.append(f"{e['scenario']} at {e['size']}: {e['on_file_current']} of {e['required']} for the current "
                           f"code {e['current_code']} (missing: {e['missing_current']}); other code on file: {others}")
    if v10a is None:
        missing.append("V10(a): no v10a.json under the records directory")
    for h in held:
        if not h["world_coded"]:
            missing.append(f"{h['scenario']}: world not coded; no held-out evidence of any kind")
    summary = {
        "records_directory_note": "paths are relative to the --out directory",
        "verdict_scope": ("DEVELOPMENT ONLY. No held-out scenario has been coded or run. No screening method is "
                          "selected and no candidate is called eligible: SIM_PREREG section 7 makes the choice "
                          "once, after the first confirmation run in which a candidate is eligible."),
        "include_stale": include_stale,
        "runs": [{k: v for k, v in e.items() if not k.startswith("_")} for e in entries],
        "criteria": rows,
        "screening_candidates": candidates,
        "components": components,
        "code_properties": CODE_PROPERTIES,
        "held_out": held,
        "held_out_runs_on_record": sum(h["runs_on_record"] for h in held),
        "missing_or_unverified": missing,
    }
    return summary


def _fmt(x, d=4):
    return "-" if x is None else f"{x:.{d}f}"


def markdown(s: dict) -> str:
    L = ["# Manhattan simulation: development status (read-only)", "",
         f"**{s['verdict_scope']}**", "",
         "Written by `python -m manhattan.sim.dev_status`" + (" with `--include-stale`" if s["include_stale"] else "")
         + ". Synthetic data only.", "", "## 1. Runs of the development plan", "",
         "| scenario | size | code route | current code | on file (current code) | pre-registered | state | missing | other code on file |",
         "|---|---|---|---|---|---|---|---|---|"]
    for e in s["runs"]:
        others = "; ".join(f"{o['replications']} × `{o['code']}`" + (f" step {o['review_step']}" if o["review_step"] is not None else "")
                           for o in e["other_code"]) or "-"
        L.append(f"| {e['scenario']} | {e['size']} | {e['code_route']} | `{e['current_code']}` | {e['on_file_current']} | "
                 f"{e['required']} | {e['state']} | {e['missing_current']} | {others} |")
    L += ["", "## 2. Required criteria on development scenarios", "",
          "Only rows the pre-registrations require in that scenario. A verdict is computed only on a complete run of "
          "the current code; numbers of other code are shown as \"not decided\".", "",
          "The last column is what the metric code would say on records of other code: information for the owner, "
          "**not a verdict**.", "",
          "| scenario | size | criterion | candidate | what | estimate | 95% interval | threshold | verdict | on other code |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in s["criteria"]:
        if not r["required"]:
            continue
        ci = f"{_fmt(r['lo'])} to {_fmt(r['hi'])}" if r.get("lo") is not None else "-"
        L.append(f"| {r['scenario']} | {r['size']} | {r['criterion']} | {CANDIDATE_NAME.get(r['candidate'], '-')} | "
                 f"{r['what']} | {_fmt(r['estimate'])} | {ci} | {r['threshold']} | {r['verdict']} | "
                 f"{r.get('computed_on_other_code') or '-'} |")
    L += ["", "## 3. Screening candidates: the development half of SIM_PREREG section 7 step 1", "",
          "Eligibility also needs the same criteria on the held-out scenarios of a confirmation run, which has not "
          "happened. **No candidate is eligible or selected here**, and the power comparison of step 2 is not computed.", "",
          "| candidate | criteria | development state | required rows by category | runs not complete | held-out half | eligible |",
          "|---|---|---|---|---|---|---|"]
    for c, g in s["screening_candidates"].items():
        L.append(f"| {CANDIDATE_NAME[c]} | {', '.join(g['criteria'])} | {g['state']} | "
                 f"{', '.join(f'{k}: {v}' for k, v in g['rows'].items()) or '-'} | {', '.join(g['runs_not_complete']) or '-'} | "
                 f"{g['held_out_half']} | {g['eligible']} |")
    L += ["", "## 4. Components (SIM_PREREG section 8.1 rule 2)", "",
          "| component | development state | required rows by category | runs not complete | note |", "|---|---|---|---|---|"]
    for name, g in s["components"].items():
        L.append(f"| {name} | {g['state']} | {', '.join(f'{k}: {v}' for k, v in g['rows'].items()) or '-'} | "
                 f"{', '.join(g['runs_not_complete']) or '-'} | {g['note'] or '-'} |")
    L += ["", "Code properties checked by the test suite, not by runs: "
          + "; ".join(f"{k} ({v})" for k, v in s["code_properties"].items()) + ".", "",
          "## 5. Held-out scenarios", "",
          "| scenario | pre-registration | sizes | world coded | runs on record | refusals on record |", "|---|---|---|---|---|---|"]
    for h in s["held_out"]:
        L.append(f"| {h['scenario']} | {h['pre_registration']} | {', '.join(h['sizes'])} | {'yes' if h['world_coded'] else 'no'} | "
                 f"{h['runs_on_record']} | {h['refusals_on_record']} |")
    L += ["", "## 6. Missing or unverified evidence", ""] + [f"- {m}" for m in s["missing_or_unverified"]]
    L += ["", "## 7. Record files read (SHA-256)", ""]
    for e in s["runs"]:
        for name, h in e["files"].items():
            L.append(f"- `{e['code_route']}/{name}`: `{h}`")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.sim.dev_status", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=run.OUT, help="the records directory (read only)")
    ap.add_argument("--include-stale", action="store_true",
                    help="show the numbers of complete runs made by other code (every verdict: not decided)")
    ap.add_argument("--md", type=Path, help="write the Markdown here (default: print it)")
    ap.add_argument("--json", type=Path, help="also write the JSON here")
    a = ap.parse_args(argv)
    s = build(a.out, a.include_stale)
    text = markdown(s)
    if a.md:
        a.md.write_text(text, encoding="utf-8")
    else:
        print(text)
    if a.json:
        a.json.write_text(json.dumps(s, indent=1, sort_keys=True, default=float) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

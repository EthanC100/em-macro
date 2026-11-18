"""The technology-equities hypothesis catalogue (``catalogue.yaml``): loading, validation, ranking and rendering.

    python -m manhattan.equities.catalogue check          # validate; exit 1 on any problem
    python -m manhattan.equities.catalogue render         # Markdown table to stdout
    python -m manhattan.equities.catalogue render --out docs/manhattan/equities/HYPOTHESIS_CATALOGUE.md

Each entry is a hypothesis **family** draft (ARCHITECTURE §3: one mechanism, one sign, one counterparty) with the
programme's extra fields (data, availability risks, baselines, costs, validation requirements). ``family_draft``
turns an entry into a Manhattan family spec and checks it with ``manhattan.spec.validate_family``; the draft is
**not** registered or frozen (freezing is Ethan's: hard rule 4), and is marked ``status: draft``.

**Rankings are qualitative.** Six 1–5 judgements (5 the favourable end) made before any data were examined.
``priority`` orders families by a declared lexicographic rule: leakage safety and data feasibility gate first (a
family that cannot be tested point in time is not a priority however plausible), then plausibility, distinctiveness,
cost and simplicity. It is a research-ordering device, not an expected return, and it does not enter any
statistical rule.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

from manhattan import spec as S

from .sources import DATASET_KINDS

PATH = Path(__file__).with_name("catalogue.yaml")
RESEARCH_FAMILIES = ("A_relative_value", "B_analogues", "C_earnings", "D_diffusion", "E_factor", "F_macro")
APPROACHES = ("relative_value", "directional")
HORIZONS = ("days", "weeks", "months", "quarters")
LEVELS = ("low", "medium", "high")
RANKS = ("economic_plausibility", "data_feasibility", "research_cost", "implementation_simplicity",
         "distinctiveness", "leakage_safety")
REQUIRED = ("id", "name", "research_family", "approach", "mechanism_class", "sign", "rationale", "counterparty",
            "target_universe", "required_data", "availability_risks", "signal_concept", "holding_horizon",
            "horizon_bucket", "baselines", "confounders", "transaction_costs", "cost_notes",
            "validation_requirements", "failure_conditions", "kill_condition", "tail_exposure",
            "implementation_complexity", "grouped_variants", "ranking")
_ID = re.compile(r"^TE-([A-F])\d{2}$")
# a catalogue states no performance: no percentages, Sharpe ratios or return figures
_PERF = re.compile(r"(\d\s*%|sharpe\s*(ratio)?\s*(of|=|:)?\s*\d|\d+\s*(bp|bps)\b|annuali[sz]ed return of)", re.I)


def load(path: Path = PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def validate(cat: dict) -> list[str]:
    errs = []
    if cat.get("status") != "draft":
        errs.append("catalogue status must be 'draft' (nothing in it is evidence)")
    fams = cat.get("families") or []
    ids = [f.get("id") for f in fams]
    if len(set(ids)) != len(ids):
        errs.append("duplicate family ids")
    names = [str(f.get("name", "")).strip().lower() for f in fams]
    if len(set(names)) != len(names):
        errs.append("duplicate family names (near-identical families must be grouped)")
    for f in fams:
        fid = f.get("id", "?")
        for k in REQUIRED:
            v = f.get(k)
            if v is None or (isinstance(v, (str, list, dict)) and not v):
                errs.append(f"{fid}: '{k}' is required")
        m = _ID.match(str(fid))
        if not m:
            errs.append(f"{fid}: id must be TE-<A-F><2 digits>")
        elif f.get("research_family", "")[:1] != m.group(1):
            errs.append(f"{fid}: id letter does not match research_family")
        if f.get("research_family") not in RESEARCH_FAMILIES:
            errs.append(f"{fid}: research_family must be one of {RESEARCH_FAMILIES}")
        if f.get("approach") not in APPROACHES:
            errs.append(f"{fid}: approach must be one of {APPROACHES}")
        if f.get("mechanism_class") not in S.MECHANISM_CLASSES:
            errs.append(f"{fid}: mechanism_class must be one of {S.MECHANISM_CLASSES}")
        if f.get("sign") not in S.SIGNS:
            errs.append(f"{fid}: sign must be '+' or '-'")
        if f.get("horizon_bucket") not in HORIZONS:
            errs.append(f"{fid}: horizon_bucket must be one of {HORIZONS}")
        for k in ("transaction_costs", "implementation_complexity"):
            if f.get(k) not in LEVELS:
                errs.append(f"{fid}: {k} must be one of {LEVELS}")
        bad = [d for d in f.get("required_data") or [] if d not in DATASET_KINDS]
        if bad:
            errs.append(f"{fid}: unknown data kinds {bad} (declare them in manhattan.equities.sources)")
        r = f.get("ranking") or {}
        if set(r) != set(RANKS):
            errs.append(f"{fid}: ranking must have exactly {RANKS}")
        elif any(isinstance(r[k], bool) or not isinstance(r[k], int) or not 1 <= r[k] <= 5 for k in RANKS):
            errs.append(f"{fid}: rankings are integers from 1 to 5")
        text = yaml.safe_dump(f)
        if _PERF.search(text):
            errs.append(f"{fid}: states a performance figure ({_PERF.search(text).group(0)!r})")
        try:
            e = S.validate_family(family_draft(f))
            errs += [f"{fid}: {x}" for x in e]
        except S.SpecError as exc:
            errs.append(f"{fid}: {exc}")
    return errs


def family_draft(f: dict) -> dict:
    """A Manhattan family spec built from a catalogue entry: a draft, never registered or frozen here."""
    return S.family(mechanism=" ".join(str(f["rationale"]).split()), mechanism_class=f["mechanism_class"],
                    sign=f["sign"], counterparty=" ".join(str(f["counterparty"]).split()),
                    kill_condition=" ".join(str(f["kill_condition"]).split()),
                    tail_exposure=" ".join(str(f["tail_exposure"]).split()),
                    catalogue_id=f["id"], programme="technology_equities", approach=f["approach"],
                    status="draft")


def priority_key(f: dict) -> tuple:
    r = f["ranking"]
    gate = min(r["leakage_safety"], r["data_feasibility"])
    return (-gate, -r["economic_plausibility"], -r["distinctiveness"], -r["research_cost"],
            -r["implementation_simplicity"], f["id"])


def prioritised(cat: dict) -> list[dict]:
    return sorted(cat["families"], key=priority_key)


def render(cat: dict) -> str:
    fams = cat["families"]
    out = ["# Technology equities: hypothesis-family catalogue", "",
           "Generated from `manhattan/equities/catalogue.yaml` by `python -m manhattan.equities.catalogue render`. "
           "Do not edit by hand.", "",
           "**Status: draft.** Every row is an untested hypothesis family. Nothing here is evidence, and no "
           "performance figure is stated. Rankings are qualitative 1–5 judgements made before any data were "
           "examined (5 is the favourable end); the priority order is a research-ordering device, not an expected "
           "return.", "",
           f"{len(fams)} families: " + ", ".join(
               f"{rf} {sum(1 for f in fams if f['research_family'] == rf)}" for rf in RESEARCH_FAMILIES)
           + f"; relative value {sum(1 for f in fams if f['approach'] == 'relative_value')}, directional "
           f"{sum(1 for f in fams if f['approach'] == 'directional')}.", "",
           "## Priority order", "",
           "Lexicographic: min(leakage safety, data feasibility), then plausibility, distinctiveness, research cost, "
           "simplicity.", "",
           "| # | id | family | approach | sign | horizon | costs | plaus. | data | cost | simpl. | distinct. | "
           "leak-safe |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, f in enumerate(prioritised(cat), 1):
        r = f["ranking"]
        out.append(f"| {i} | {f['id']} | {f['name']} | {f['approach']} | {f['sign']} | {f['holding_horizon']} | "
                   f"{f['transaction_costs']} | {r['economic_plausibility']} | {r['data_feasibility']} | "
                   f"{r['research_cost']} | {r['implementation_simplicity']} | {r['distinctiveness']} | "
                   f"{r['leakage_safety']} |")
    out += ["", "## Families", ""]
    for f in fams:
        out += [f"### {f['id']} {f['name']}", "",
                f"*{f['research_family']}, {f['approach']}, mechanism class {f['mechanism_class']}, sign "
                f"{f['sign']}, horizon {f['holding_horizon']}, implementation {f['implementation_complexity']}.*", "",
                f"**Rationale.** {' '.join(str(f['rationale']).split())}", "",
                f"**Counterparty.** {' '.join(str(f['counterparty']).split())}", "",
                f"**Universe.** {' '.join(str(f['target_universe']).split())}", "",
                f"**Data.** {', '.join(f['required_data'])}", "",
                "**Availability risks.** " + " ".join(f"({i}) {x}" for i, x in enumerate(f['availability_risks'], 1)),
                "", f"**Signal concept.** {' '.join(str(f['signal_concept']).split())}", "",
                "**Baselines.** " + "; ".join(f["baselines"]), "",
                "**Confounders.** " + "; ".join(f["confounders"]), "",
                f"**Costs ({f['transaction_costs']}).** {' '.join(str(f['cost_notes']).split())}", "",
                "**Validation requirements.** " + " ".join(
                    f"({i}) {x}" for i, x in enumerate(f['validation_requirements'], 1)), "",
                "**Failure conditions.** " + " ".join(f"({i}) {x}" for i, x in enumerate(f['failure_conditions'], 1)),
                "", f"**Kill condition.** {' '.join(str(f['kill_condition']).split())}", "",
                f"**Tail exposure.** {' '.join(str(f['tail_exposure']).split())}", "",
                f"**Grouped variants.** {' '.join(str(f['grouped_variants']).split())}", ""]
    return "\n".join(out).rstrip()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m manhattan.equities.catalogue")
    ap.add_argument("command", choices=("check", "render"))
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    cat = load()
    errs = validate(cat)
    if a.command == "check":
        for e in errs:
            print(e)
        print(f"{len(cat['families'])} families, {len(errs)} problems")
        return 1 if errs else 0
    if errs:
        print("\n".join(errs), file=sys.stderr)
        return 1
    text = render(cat) + "\n"
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

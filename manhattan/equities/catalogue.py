"""The technology-equities hypothesis catalogue (``catalogue.yaml``): loading, validation, ranking and rendering.

    python -m manhattan.equities.catalogue check          # validate; exit 1 on any problem
    python -m manhattan.equities.catalogue render         # Markdown table to stdout
    python -m manhattan.equities.catalogue render --out docs/manhattan/equities/HYPOTHESIS_CATALOGUE.md

Each entry is a hypothesis **family** draft (ARCHITECTURE §3: one mechanism, one sign, one counterparty) with the
programme's extra fields (data, availability risks, baselines, costs, validation requirements). ``family_draft``
turns an entry into a Manhattan family spec and checks it with ``manhattan.spec.validate_family``; the draft is
**not** registered or frozen (freezing is Ethan's: hard rule 4), and is marked ``status: draft``.

**Rankings are qualitative.** Six 1–5 judgements (5 the favourable end) made before any data were examined.
``priority`` orders families by a declared lexicographic rule (S8 R3): first the **affordable data tier**
(``data_tier``: prices and EDGAR, then EDGAR text, then unavailable history), so the order reflects what can
actually be tested on the budget; then min(leakage safety, data feasibility), plausibility, distinctiveness, cost
and simplicity. It is a research-ordering device, not an expected return, and it does not enter any statistical rule.

**Declared, not enforced.** ``shared_family`` groups entries that test overlapping mechanisms. It is a declaration
in a draft catalogue: ``family_draft`` carries it with ``shared_family_enforced: False``, and nothing in freezing or
attempt accounting reads it today. Enforcing it (one Manhattan family per group, or ``parent_family`` links, and one
multiple-testing count) is part of a future freeze, which is Ethan's. Grouping never removes an entry from the
denominator: all 39 entries remain, and any attempt on any of them would count.
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
NT_PATH = Path(__file__).with_name("catalogue_nontech.yaml")          # issue #102: the non-technology track
RESEARCH_FAMILIES = ("A_relative_value", "B_analogues", "C_earnings", "D_diffusion", "E_factor", "F_macro")
NT_RESEARCH_FAMILIES = ("V_value", "Q_quality", "M_momentum", "R_revisions", "L_low_risk")
# Each programme is one equity research track (manhattan.tracks) with its own catalogue, id prefix and families.
PROGRAMMES = {
    "technology_equities": {"prefix": "TE", "research_families": RESEARCH_FAMILIES, "path": PATH, "extra": ()},
    "non_technology_equities": {"prefix": "NT", "research_families": NT_RESEARCH_FAMILIES, "path": NT_PATH,
                                "extra": ("cross_track", "sector_scope", "cross_sector_validation")},
}
CROSS_TRACK_ROLES = ("related_not_designated", "designated_replication")
SECTOR_SCOPES = ("all_non_technology", "non_technology_ex_financials_real_estate")
_XM = re.compile(r"^XM-[A-Z][A-Z-]+$")
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
_SF = re.compile(r"^SF-[A-Z][A-Z-]+$")

# Data feasibility tiers (S8 correction round). What a family needs, against what can realistically be had point in
# time on a budget of about S$500/month (DATA_ACQUISITION.md). Unverified until the checks there are done.
PRICE_KINDS = frozenset({"security_master", "prices_daily", "corporate_actions", "delisting_returns", "market_calendar",
                         "index_membership", "fx_rates", "macro_pit"})          # one paid price source + public macro
EDGAR_KINDS = frozenset({"fundamentals_pit", "segment_reporting", "earnings_events", "classification_history"})
EDGAR_TEXT_KINDS = frozenset({"regulatory_filings_text", "customer_concentration", "guidance_events"})
FREE_PUBLIC_KINDS = frozenset({"short_interest"})                               # FINRA publications
UNAVAILABLE_KINDS = frozenset({"analyst_estimates_pit", "borrow_availability", "options_implied_vol",
                               "earnings_call_text", "relationship_graph", "patents", "product_releases",
                               "developer_adoption", "cloud_capex", "semiconductor_supply_chain", "hiring",
                               "product_adoption"})
TIERS = ("prices_and_edgar", "prices_and_edgar_text", "needs_unavailable_history")
# a catalogue states no performance: no percentages, Sharpe ratios or return figures
_PERF = re.compile(r"(\d\s*%|sharpe\s*(ratio)?\s*(of|=|:|above|near)?\s*\d|\d+\s*(bp|bps)\b|annuali[sz]ed return of"
                   r"|information ratio\s*(of|=|:)?\s*\d|t-stat(istic)?\s*(of|=|:)?\s*\d|earn(s|ed)\s+\d)", re.I)


def data_tier(f: dict) -> tuple[str, tuple]:
    """(tier, the kinds that block it). ``prices_and_edgar``: a survivorship-free price source, EDGAR structured data
    (filing acceptance times, XBRL facts, 8-K item 2.02 times as a conservative release proxy, SIC codes from filing
    headers as a classification proxy) and free public series. ``prices_and_edgar_text``: also needs EDGAR text
    parsed point in time. ``needs_unavailable_history``: needs a history that is not affordable or not verifiably
    point in time (estimates, borrow, implied volatility, call transcripts, relationship graphs, alternative data);
    it can be researched only by forward collection or after a data decision."""
    need = set(f.get("required_data") or [])
    blocked = tuple(sorted(need & UNAVAILABLE_KINDS))
    if blocked:
        return "needs_unavailable_history", blocked
    unknown = need - PRICE_KINDS - EDGAR_KINDS - EDGAR_TEXT_KINDS - FREE_PUBLIC_KINDS
    if unknown:
        return "needs_unavailable_history", tuple(sorted(unknown))
    if need & EDGAR_TEXT_KINDS:
        return "prices_and_edgar_text", ()
    return "prices_and_edgar", ()


def load(path: Path = PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def programme_of(cat: dict) -> str:
    """The research programme (equity track) a catalogue belongs to; technology when the catalogue predates
    issue #102 and names none."""
    return cat.get("programme", "technology_equities")


def validate(cat: dict) -> list[str]:
    errs = []
    prog = programme_of(cat)
    if prog not in PROGRAMMES:
        return [f"unknown programme {prog!r}"]
    conf = PROGRAMMES[prog]
    id_re = re.compile(rf"^{conf['prefix']}-([A-Z])\d{{2}}$")
    if cat.get("track", prog) != prog:
        errs.append("a catalogue's track must equal its programme (one catalogue, one track)")
    if cat.get("status") != "draft":
        errs.append("catalogue status must be 'draft' (nothing in it is evidence)")
    fams = cat.get("families") or []
    ids = [f.get("id") for f in fams]
    if len(set(ids)) != len(ids):
        errs.append("duplicate family ids")
    names = [str(f.get("name", "")).strip().lower() for f in fams]
    if len(set(names)) != len(names):
        errs.append("duplicate family names (near-identical families must be grouped)")
    shared: dict = {}
    for f in fams:
        if f.get("shared_family"):
            shared.setdefault(f["shared_family"], []).append(f.get("id"))
    for g, members in shared.items():
        if len(members) < 2:
            errs.append(f"{g}: a shared family needs at least two members ({members})")
    for f in fams:
        fid = f.get("id", "?")
        for k in REQUIRED + conf["extra"]:
            v = f.get(k)
            if v is None or (isinstance(v, (str, list, dict)) and not v):
                errs.append(f"{fid}: '{k}' is required")
        m = id_re.match(str(fid))
        if not m:
            errs.append(f"{fid}: id must be {conf['prefix']}-<letter><2 digits>")
        elif f.get("research_family", "")[:1] != m.group(1):
            errs.append(f"{fid}: id letter does not match research_family")
        if f.get("research_family") not in conf["research_families"]:
            errs.append(f"{fid}: research_family must be one of {conf['research_families']}")
        if conf["extra"]:
            errs += [f"{fid}: {e}" for e in _nontech_fields(f)]
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
        bad = [d for d in (f.get("required_data") or []) + (f.get("optional_data") or []) if d not in DATASET_KINDS]
        if bad:
            errs.append(f"{fid}: unknown data kinds {bad} (declare them in manhattan.equities.sources)")
        if set(f.get("optional_data") or []) & set(f.get("required_data") or []):
            errs.append(f"{fid}: a kind is both required and optional")
        r = f.get("ranking") or {}
        if set(r) != set(RANKS):
            errs.append(f"{fid}: ranking must have exactly {RANKS}")
        elif any(isinstance(r[k], bool) or not isinstance(r[k], int) or not 1 <= r[k] <= 5 for k in RANKS):
            errs.append(f"{fid}: rankings are integers from 1 to 5")
        sf = f.get("shared_family")
        if sf is not None and not _SF.match(str(sf)):
            errs.append(f"{fid}: shared_family must look like SF-NAME")
        text = yaml.safe_dump(f)
        if _PERF.search(text):
            errs.append(f"{fid}: states a performance figure ({_PERF.search(text).group(0)!r})")
        try:
            e = S.validate_family(family_draft(f, programme=prog))
            errs += [f"{fid}: {x}" for x in e]
        except S.SpecError as exc:
            errs.append(f"{fid}: {exc}")
    return errs


def _nontech_fields(f: dict) -> list[str]:
    errs = []
    ct = f.get("cross_track")
    if not isinstance(ct, dict) or set(ct) != {"mechanism", "technology_counterpart", "technology_shared_family",
                                               "role"}:
        return ["cross_track needs exactly mechanism, technology_counterpart, technology_shared_family and role"]
    if not _XM.match(str(ct["mechanism"])):
        errs.append("cross_track.mechanism must look like XM-NAME")
    if ct["role"] not in CROSS_TRACK_ROLES:
        errs.append(f"cross_track.role must be one of {CROSS_TRACK_ROLES}")
    if ct["technology_counterpart"] is not None and not _ID.match(str(ct["technology_counterpart"])):
        errs.append("cross_track.technology_counterpart must be a TE id or null")
    if ct["technology_counterpart"] is None and ct["role"] == "designated_replication":
        errs.append("a designated replication needs a technology counterpart")
    if f.get("sector_scope") not in SECTOR_SCOPES:
        errs.append(f"sector_scope must be one of {SECTOR_SCOPES}")
    if f.get("cross_sector_validation") != "leave_one_sector_out":
        errs.append("cross_sector_validation must be leave_one_sector_out")
    if "sector-neutral" not in " ".join(str(f.get("grouped_variants", "")).split()):
        errs.append("grouped_variants must include the sector-neutral expression (one family, not two)")
    return errs


def cross_track_report(tech: dict, nontech: dict) -> dict:
    """The two equity catalogues side by side: per-track and combined family counts, and the cross-track links.

    No link removes a family from any count. A linked pair tests one mechanism in two tracks, so the pair is
    **dependent**: a result in one track is never counted as independent confirmation of the other unless the link
    was designated as a replication before either was tested. ``problems`` lists every link that does not resolve."""
    te = {f["id"]: f for f in tech.get("families", [])}
    nt = nontech.get("families", [])
    problems, links = [], []
    mech_seen: dict = {}
    for f in nt:
        ct = f.get("cross_track") or {}
        m = ct.get("mechanism")
        if m in mech_seen:
            problems.append(f"{f['id']}: mechanism {m} already used by {mech_seen[m]} (one family per mechanism)")
        mech_seen[m] = f["id"]
        cp = ct.get("technology_counterpart")
        if cp is not None and cp not in te:
            problems.append(f"{f['id']}: technology counterpart {cp} is not in the technology catalogue")
        elif cp is not None and ct.get("technology_shared_family") != te[cp].get("shared_family"):
            problems.append(f"{f['id']}: technology_shared_family does not match {cp}'s shared_family")
        links.append({"mechanism": m, "non_technology": f["id"], "technology": cp,
                      "technology_shared_family": ct.get("technology_shared_family"), "role": ct.get("role"),
                      "independent_evidence": False if cp is not None else None})
    return {"by_track": {"technology_equities": len(te), "non_technology_equities": len(nt)},
            "combined_families": len(te) + len(nt), "links": links, "problems": problems,
            "counting_rule": "every family of both tracks stays in the combined denominator; linked pairs are "
                             "dependent and never double-counted as independent confirmation"}


def family_draft(f: dict, *, programme: str = "technology_equities") -> dict:
    """A Manhattan family spec built from a catalogue entry: a draft, never registered or frozen here. Members of a
    shared family carry ``shared_family`` so a freeze can register them as hypotheses of one family. ``programme``
    is the entry's equity research track."""
    if programme not in PROGRAMMES:
        raise S.SpecError(f"unknown programme {programme!r}")
    extra = {"shared_family": f["shared_family"], "shared_family_enforced": False} if f.get("shared_family") else {}
    if f.get("cross_track"):
        extra.update(cross_track_mechanism=f["cross_track"]["mechanism"],
                     cross_track_role=f["cross_track"]["role"])
    return S.family(**extra, mechanism=" ".join(str(f["rationale"]).split()), mechanism_class=f["mechanism_class"],
                    sign=f["sign"], counterparty=" ".join(str(f["counterparty"]).split()),
                    kill_condition=" ".join(str(f["kill_condition"]).split()),
                    tail_exposure=" ".join(str(f["tail_exposure"]).split()),
                    catalogue_id=f["id"], programme=programme, approach=f["approach"],
                    status="draft")


def priority_key(f: dict) -> tuple:
    r = f["ranking"]
    gate = min(r["leakage_safety"], r["data_feasibility"])
    return (TIERS.index(data_tier(f)[0]), -gate, -r["economic_plausibility"], -r["distinctiveness"], -r["research_cost"],
            -r["implementation_simplicity"], f["id"])


def prioritised(cat: dict) -> list[dict]:
    return sorted(cat["families"], key=priority_key)


_TITLES = {"technology_equities": "Technology equities", "non_technology_equities": "Non-technology equities"}


def render(cat: dict) -> str:
    fams = cat["families"]
    prog = programme_of(cat)
    conf = PROGRAMMES[prog]
    cmd = "python -m manhattan.equities.catalogue render" + ("" if prog == "technology_equities"
                                                            else f" --programme {prog}")
    out = [f"# {_TITLES[prog]}: hypothesis-family catalogue", "",
           f"Generated from `manhattan/equities/{conf['path'].name}` by `{cmd}`. "
           "Do not edit by hand.", "",
           "**Status: draft.** Every row is an untested hypothesis family. Nothing here is evidence, and no "
           "performance figure is stated. Rankings are qualitative 1–5 judgements made before any data were "
           "examined (5 is the favourable end); the priority order is a research-ordering device, not an expected "
           "return.", "",
           f"{len(fams)} families: " + ", ".join(
               f"{rf} {sum(1 for f in fams if f['research_family'] == rf)}" for rf in conf["research_families"])
           + f"; relative value {sum(1 for f in fams if f['approach'] == 'relative_value')}, directional "
           f"{sum(1 for f in fams if f['approach'] == 'directional')}.", "",
           "**Multiple-testing denominator.** All " + str(len(fams)) + " entries remain (no id removed or renumbered). "
           "Shared families group related entries; they never shrink the count of entries, and any attempt on any "
           "entry would count.", "",
           "## Priority order", "",
           "Lexicographic: affordable data tier first (prices and EDGAR, then EDGAR text, then unavailable history), "
           "then min(leakage safety, data feasibility), plausibility, distinctiveness, research cost, simplicity.", "",
           "| # | id | family | shared family | data tier | approach | sign | horizon | costs | plaus. | data | cost | "
           "simpl. | distinct. | leak-safe |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, f in enumerate(prioritised(cat), 1):
        r = f["ranking"]
        out.append(f"| {i} | {f['id']} | {f['name']} | {f.get('shared_family', '')} | {data_tier(f)[0]} | "
                   f"{f['approach']} | {f['sign']} | {f['holding_horizon']} | "
                   f"{f['transaction_costs']} | {r['economic_plausibility']} | {r['data_feasibility']} | "
                   f"{r['research_cost']} | {r['implementation_simplicity']} | {r['distinctiveness']} | "
                   f"{r['leakage_safety']} |")
    shared: dict = {}
    for f in fams:
        if f.get("shared_family"):
            shared.setdefault(f["shared_family"], []).append(f["id"])
    out += ["", "## Shared hypothesis families", "",
            "Entries that test overlapping mechanisms or near-identical signals. Their ids are kept (drafts). "
            "**This grouping is declared, not enforced:** nothing in freezing or attempt accounting reads it today. "
            "If frozen, each group should be registered as one Manhattan family (or linked by `parent_family`) and "
            "counted together for multiple testing; that enforcement is part of a future freeze (Ethan's).", "",
            "| shared family | members |", "|---|---|"]
    out += [f"| {g} | {', '.join(m)} |" for g, m in sorted(shared.items())]
    out += ["", "## Data feasibility", "",
            "Computed from each family's required data (`catalogue.data_tier`); unverified until the checks of "
            "DATA_ACQUISITION.md section 4 are done.", "",
            "- **prices_and_edgar**: one survivorship-free price source, EDGAR structured data and free public "
            "series.",
            "- **prices_and_edgar_text**: also EDGAR text parsed point in time.",
            "- **needs_unavailable_history**: a history that is unaffordable or not verifiably point in time; forward "
            "collection or a data decision first.", "",
            "Caveat: relative-value families in the first two tiers do not list borrow history among their data, but "
            "their short legs need it. Without an affordable borrow history they can be studied only with explicit, "
            "flagged borrow assumptions (a `costs.BorrowBook` with no record refuses the short), and any such result "
            "says so.", "",
            "| tier | families | blocked by |", "|---|---|---|"]
    for t in TIERS:
        ids = [f["id"] for f in fams if data_tier(f)[0] == t]
        blocks = sorted({k for f in fams if data_tier(f)[0] == t for k in data_tier(f)[1]})
        out.append(f"| {t} | {len(ids)}: {', '.join(ids)} | {', '.join(blocks)} |")
    out += ["", "## Families", ""]
    for f in fams:
        tier, blocks = data_tier(f)
        out += [f"### {f['id']} {f['name']}", "",
                f"*{f['research_family']}, {f['approach']}, mechanism class {f['mechanism_class']}, sign "
                f"{f['sign']}, horizon {f['holding_horizon']}, implementation {f['implementation_complexity']}; "
                f"data tier {tier}{' (blocked by ' + ', '.join(blocks) + ')' if blocks else ''}"
                f"{'; shared family ' + f['shared_family'] if f.get('shared_family') else ''}.*", "",
                f"**Rationale.** {' '.join(str(f['rationale']).split())}", "",
                f"**Counterparty.** {' '.join(str(f['counterparty']).split())}", "",
                f"**Universe.** {' '.join(str(f['target_universe']).split())}", "",
                f"**Data.** {', '.join(f['required_data'])}", "",
                "**Availability risks.** " + " ".join(f"({i}) {x}" for i, x in enumerate(f['availability_risks'], 1)),
                "", f"**Signal concept.** {' '.join(str(f['signal_concept']).split())}", ""]
        if f.get("optional_data"):
            out += [f"**Optional data (variants only; not in the tier).** {', '.join(f['optional_data'])}", ""]
        out += [
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
    ap.add_argument("--programme", choices=tuple(PROGRAMMES), default="technology_equities")
    a = ap.parse_args(argv)
    cat = load(PROGRAMMES[a.programme]["path"])
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

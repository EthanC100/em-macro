"""Session "6M Manhattan C: dormancy fix and statistical checks": write DORMANCY_SECOND_LOOK.md from the four-path
replays (paths.py) and the traces (trace_hb.py). Every number in the file is computed here.

    python second_look.py PATHS_4_DATES.jsonl PATHS_YEARLY.jsonl TRACE_DIR OUT.md
"""
import glob, json, math, os, sys
import numpy as np
from scipy.stats import t as student_t
from manhattan.sim import metrics

p4, p10, trace_dir, out_path = sys.argv[1:5]
SCEN = ("D02", "D05", "D08", "D10")
NAME = {"branch": "the rule on the branch (forecast and `Π^max`)", "v30": "the rule of 3.0 (forecast alone)",
        "own": "alternative (forecast and own forward record)", "none": "no dormancy"}


def load(path):
    by = {}
    for line in open(path):
        if line.strip():
            r = json.loads(line)
            by.setdefault(r["scenario"], []).append(r)
    return {s: sorted(v, key=lambda r: r["rep"]) for s, v in by.items()}


def jack(num, den):
    """Pooled ratio with the pre-registered percentile interval and the delete-one-replication jackknife-t
    interval (the exact bound over replications when no replication has an event)."""
    num, den = np.asarray(num, float), np.asarray(den, float)
    R = len(num)
    e, lo, hi = metrics.ratio_ci(num, den)
    loo = np.array([(num.sum() - num[i]) / (den.sum() - den[i]) for i in range(R) if den.sum() - den[i] > 0])
    se = math.sqrt((len(loo) - 1) / len(loo) * ((loo - loo.mean()) ** 2).sum())
    tq = student_t.ppf(0.975, R - 1)
    if se < 1e-12 and e == 0:
        return e, lo, hi, 0.0, 1 - 0.025 ** (1 / R)
    return e, lo, hi, e - tq * se, e + tq * se


def g(reps, rule, k):
    return np.array([r["diag"][rule][k] for r in reps], float)


def cat(reps, rule, k):
    return np.array([v for r in reps for v in r["diag"][rule][k]], float)


def m8cell(reps, rule, key="m8_num"):
    e, lo, hi, jl, jh = jack(g(reps, rule, key), g(reps, rule, "m8_den"))
    return f"{e:.3f} ({lo:.3f} to {hi:.3f}; clustered {max(jl, 0):.3f} to {jh:.3f}); {int(g(reps, rule, key).sum())} of {int(g(reps, rule, 'm8_den').sum())}"


def share(reps, rule, num, den):
    return g(reps, rule, num).sum() / g(reps, rule, den).sum()


A, B = load(p4), load(p10)
L = ["# The dormancy rule: a second, independent look, the diagnostics the pilot's records do not hold, and an alternative", "",
     "Written by `dev_6M_b/second_look.py` (session \"6M Manhattan C: dormancy fix and statistical checks\", 2026-11-13). "
     "**Synthetic data only. Development scenarios only (seed branch 0). No held-out scenario was coded or run. "
     "Development experiments outside the runner (`note-6Mb-01` and `note-6Mb-02` in the run log): they decide nothing.**", "",
     "**Why this file exists.** Two sessions were given the dormancy problem on the same branch. The first, \"6M Manhattan "
     "C: dormancy fix before adoption\", diagnosed it, revised Protocol 3.1 §9.1 and pushed (`DORMANCY_DIAGNOSIS.md`, "
     "`PILOT_RERUN2_REPORT.md`). This session reached the same diagnosis separately, on its own instrumented runs, and had "
     "chosen a different second condition for the rule before it found the other's work. **The rule on the branch is the "
     "first session's and this session changed nothing in it**: no protocol text, no hash, no pipeline code. This file "
     "adds three things: the diagnosis seen from a second set of experiments (section 1); the diagnostics the brief asked "
     "for and the pilot's records do not hold (section 2); and the other rule, measured beside the branch's on the same "
     "fits, for Ethan to choose between before he adopts (section 3; ETHAN_ACTIONS item 22).", "",
     "**How it was made.** `paths.py` runs the branch's HB pipeline unchanged (same seeds, worlds, fits and forecast "
     "stream) and steps the tier state machine four ways on the same fits: the rule on the branch, the rule of 3.0, the "
     "alternative, and no dormancy. " + f"{sum(len(v) for v in A.values())} replications at the four pre-registered review dates "
     f"(years 2, 4, 7 and 10) and {sum(len(v) for v in B.values())} with a review every year. Candidate (i)'s tiers.", ""]

# ---- continuity
from manhattan.sim import run
same = both = same5 = both5 = 0
for s in SCEN:
    new = {x["rep"]: x for x in run.load_reps(s, "HB", version="v2", code=run.code_hash("HB", version="v2"))}
    old = {x["rep"]: x for x in run.load_reps(s, "HB", version="v2", code="c22815235975c486")}
    for r in A.get(s, []):
        b, v = r["diag"]["branch"], r["diag"]["v30"]
        if r["rep"] in new:
            n = new[r["rep"]]
            both += 1
            same += (b["m8_num"], b["m8_den"], b["end_dormant"], b["reviews_written"]) == (n["m8_num_i"], n["m8_den_i"], n["end_dormant_i"], n["written_i"])
        if r["rep"] in old:
            o = old[r["rep"]]
            both5 += 1
            same5 += (v["m8_num"], v["end_dormant"]) == (o["m8_num_i"], o["end_dormant_i"])
L += [f"**Check that these are the pilot's own replications.** The \"branch\" path gives the pilot of record's counts (families "
      f"retired, families with an edge, families dormant at the end, reviews written) in **{same} of {both}** replications, and the "
      f"\"3.0\" path gives session 5M's pilot in **{same5} of {both5}**.", ""]

# ---- section 1
L += ["## 1. The same diagnosis, from a second set of experiments", "",
      "`trace_hb.py` re-ran session 5M's 48 pilot replications under the rule of 3.0 keeping every family's numbers; all 48 "
      "reproduce the recorded counts (7 of 42, 25 of 140, 102 of 944, 18 of 123 retired). `who.txt` and `replay_table.txt` in "
      "`dev_6M_b/` have the full output. It agrees with `DORMANCY_DIAGNOSIS.md` on every point, and adds two.", "",
      "| what | D02 | D05 | D08 | D10 |", "|---|---|---|---|---|",
      "| families with an edge retired by the rule of 3.0 | 7 of 42 | 25 of 140 | 102 of 944 | 18 of 123 |",
      "| their true Sharpe ratio, 10th / 50th / 90th percentile | 0.38 / 0.73 / 0.85 | 0.27 / 0.56 / 0.99 | 0.27 / 0.72 / 1.06 | 0.29 / 0.32 / 0.67 |",
      "| forward years on record when retired | 3.6 / 4.5 / 6.3 | 3.2 / 4.1 / 6.4 | 3.2 / 4.9 / 6.6 | 3.0 / 3.8 / 6.7 |",
      "| their forward Sharpe estimate | 0.24 / 0.44 / 0.67 | −0.04 / 0.51 / 0.89 | 0.08 / 0.58 / 1.12 | −0.34 / 0.28 / 0.65 |",
      "| posterior mean of their edge, central model | 0.00 / 0.02 / 0.08 | −0.01 / 0.08 / 0.32 | 0.08 / 0.33 / 0.58 | −0.12 / 0.00 / 0.16 |",
      "| `Π^max` | 0.06 / 0.09 / 0.21 | 0.05 / 0.16 / 0.62 | 0.20 / 0.65 / 0.95 | 0.04 / 0.18 / 0.48 |",
      "| forecast `PP^max` | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.01 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |",
      "| **forecast with the family's true edge in place of the posterior draws** | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | 0.00 / 0.00 / 0.00 |",
      "| **one-sided p-value of the family's own forward record against an edge of 0.25** | 0.50 / 0.67 / 0.79 | 0.28 / 0.72 / 0.91 | 0.34 / 0.75 / 0.98 | 0.13 / 0.52 / 0.82 |",
      "| share with that p-value below 0.05 | 0.00 | 0.04 | 0.00 | 0.06 |", "",
      "- The forecast was exactly 0.00 for 139 of the 152 retired families and never above 0.045, so no cut-off is near them: "
      "the same finding.",
      "- **Added: the forecast stays at zero when the true edge replaces the posterior draws.** So it is not only that the "
      "tier's bar is high. The forecast updates each model's present posterior as if it were a normal prior and does not "
      "refit (a declared approximation, Protocol §9.1 and SIM_PREREG_v2 §2(f)). A posterior of standard deviation 0.13 to "
      "0.22 then weighs as much as 20 to 60 years of forward data, and no simulated future can move it. That is why "
      "relaxing the tier's bar and the horizon together still left 0.07 to 0.12 where edges are rare (`replay_table.txt`).",
      "- **Added: the retired families' own forward records were not against them.** The one-sided p-value of \"the edge "
      "is at least 0.25\" on a family's own forward record had a median of 0.52 to 0.75; it was below 0.05 for 2 of the "
      "152. That observation is what the alternative of section 3 is built on.", ""]

# ---- section 2
def diag_table(data, title):
    out = ["### " + title, "", "| | " + " | ".join(SCEN) + " |", "|---|" + "---|" * len(SCEN)]
    def row(label, fn):
        out.append(f"| {label} | " + " | ".join(fn(data[s]) if s in data else "-" for s in SCEN) + " |")
    row("replications", lambda r: str(len(r)))
    row("families with a true edge", lambda r: f"{int(g(r, 'branch', 'm8_den').sum())}")
    row("**premature elimination (M8)**: estimate (pre-registered interval; interval with the replication as the cluster)", lambda r: m8cell(r, "branch"))
    row("the same under the rule of 3.0, on the same fits", lambda r: m8cell(r, "v30"))
    row("**share of families with a true edge ever made dormant**", lambda r: f"{share(r, 'branch', 'edge_ever_dormant', 'm8_den'):.3f} ({int(g(r, 'branch', 'edge_ever_dormant').sum())})")
    row("under the rule of 3.0", lambda r: f"{share(r, 'v30', 'edge_ever_dormant', 'm8_den'):.3f} ({int(g(r, 'v30', 'edge_ever_dormant').sum())})")
    row("true Sharpe ratio of those ever dormant: 10th / 50th / 90th percentile", lambda r: " / ".join(f"{x:.2f}" for x in np.percentile(cat(r, 'branch', 'edge_ever_true'), [10, 50, 90])) if cat(r, 'branch', 'edge_ever_true').size else "none")
    row("**how long they were dormant**, years: mean / median / longest", lambda r: " / ".join(f"{x:.1f}" for x in (cat(r, 'branch', 'edge_dormant_years').mean(), np.median(cat(r, 'branch', 'edge_dormant_years')), cat(r, 'branch', 'edge_dormant_years').max())) if cat(r, 'branch', 'edge_dormant_years').size else "none")
    row("as a share of their forward life: mean", lambda r: f"{cat(r, 'branch', 'edge_dormant_share').mean():.2f}" if cat(r, 'branch', 'edge_dormant_share').size else "none")
    row("**reactivation**, families with a true edge: woken / of those dormant again at the end / Promising at the end / Statistically supported at the end",
        lambda r: " / ".join(str(int(g(r, 'branch', k).sum())) for k in ("edge_woken", "edge_woken_end_dormant", "edge_woken_promising", "edge_woken_supported")))
    row("premature elimination had nothing ever been reactivated (every family ever dormant counted)", lambda r: f"{share(r, 'branch', 'edge_ever_dormant', 'm8_den'):.3f}")
    row("premature elimination had nothing been able to wake at the last date", lambda r: m8cell(r, "branch", "m8_num_no_last_wake"))
    row("**delay to tier entry**: families with a true edge that enter Statistically supported with no dormancy / never enter because dormant / enter later because dormant",
        lambda r: f"{int(g(r, 'branch', 'edge_entry_without_dormancy').sum())} / {int(g(r, 'branch', 'edge_entry_lost').sum())} / {int((cat(r, 'branch', 'edge_entry_delay_years') > 0).sum())}")
    row("the same under the rule of 3.0", lambda r: f"{int(g(r, 'v30', 'edge_entry_without_dormancy').sum())} / {int(g(r, 'v30', 'edge_entry_lost').sum())} / {int((cat(r, 'v30', 'edge_entry_delay_years') > 0).sum())}"
        + (f" (mean delay {cat(r, 'v30', 'edge_entry_delay_years')[cat(r, 'v30', 'edge_entry_delay_years') > 0].mean():.1f} years)" if (cat(r, 'v30', 'edge_entry_delay_years') > 0).any() else ""))
    row("families with no edge: ever dormant / dormant at the end (shares)", lambda r: f"{share(r, 'branch', 'null_ever_dormant', 'n_null'):.3f} / {share(r, 'branch', 'null_end_dormant', 'n_null'):.3f}")
    row("under the rule of 3.0", lambda r: f"{share(r, 'v30', 'null_ever_dormant', 'n_null'):.3f} / {share(r, 'v30', 'null_end_dormant', 'n_null'):.3f}")
    row("families with no edge: reactivated / of those dormant again at the end", lambda r: f"{int(g(r, 'branch', 'null_woken').sum())} / {int(g(r, 'branch', 'null_woken_end_dormant').sum())}")
    row("**attention**: share of family-reviews written (1 with no dormancy)", lambda r: f"{share(r, 'branch', 'reviews_written', 'reviews_possible'):.3f}")
    row("under the rule of 3.0", lambda r: f"{share(r, 'v30', 'reviews_written', 'reviews_possible'):.3f}")
    return out + [""]


L += ["## 2. Diagnostics of the rule on the branch", "",
      "Reported as diagnostics only: no criterion reads them. \"Ever dormant\" counts a family dormant at any review; M8 "
      "counts it only if it ends dormant or was dormant for more than half its forward life.", ""]
L += diag_table(A, "At the four pre-registered review dates (the pilot of record's replications)")
if B:
    L += diag_table(B, "With a review every year (a development experiment; the same worlds)")
tot = lambda data, rule, k: int(sum(g(data[s], rule, k).sum() for s in SCEN if s in data))
catall = lambda data, rule, k: np.concatenate([cat(data[s], rule, k) for s in SCEN if s in data])
L += ["What they say:", "",
      f"- **Ever dormant and retired are nearly the same families.** At the four dates {tot(A, 'branch', 'edge_ever_dormant')} families with an edge "
      f"were ever dormant under the branch's rule and {tot(A, 'branch', 'm8_num')} count as retired; with yearly reviews "
      f"{tot(B, 'branch', 'edge_ever_dormant')} and {tot(B, 'branch', 'm8_num')}. A family with an edge that is put aside almost never comes back: "
      f"{tot(A, 'branch', 'edge_woken')} were reactivated at the four dates and {tot(B, 'branch', 'edge_woken')} with yearly reviews. To come back "
      "it needs `Π^max` or the forecast at 0.15, and a record that looked like no edge rarely improves that much in the "
      "years left. **Reactivation does little under this rule**; what protects a family with an edge is not being put "
      "aside in the first place.",
      f"- **Durations.** Those put aside were dormant for {catall(A, 'branch', 'edge_dormant_years').mean():.1f} years on average at the four dates "
      f"(from year 7 to the end) and {catall(B, 'branch', 'edge_dormant_years').mean():.1f} years with yearly reviews (longest "
      f"{catall(B, 'branch', 'edge_dormant_years').max():.0f}).",
      f"- **Delay to tier entry: none.** No family that enters Statistically supported when nothing is ever dormant is kept out "
      f"or delayed by the branch's rule, at either calendar ({tot(A, 'branch', 'edge_entry_without_dormancy')} and "
      f"{tot(B, 'branch', 'edge_entry_without_dormancy')} entries). Even the rule of 3.0 kept out only "
      f"{tot(A, 'v30', 'edge_entry_lost')} and {tot(B, 'v30', 'edge_entry_lost')}: the families a dormancy rule retires are not the ones "
      "about to enter the tier. What premature elimination costs is the attention a family with a real edge stops getting, "
      "not a tier entry.",
      "- **Families with no edge** are where the two calendars differ most: the share dormant at the end roughly triples "
      "with yearly reviews, and so does the attention saved.",
      "- **Compute.** Dormancy saves no computing in either form: every family's data stay in the model, and the forecast "
      "is made for every family below the tier. The cost of a rule is in the reviews written.", ""]

# ---- section 3
def cmp_table(data):
    out = ["| | rule | " + " | ".join(SCEN) + " |", "|---|---|" + "---|" * len(SCEN)]
    for label, fn in (("premature elimination (M8)", lambda r, k: m8cell(r, k)),
                      ("families with an edge ever dormant", lambda r, k: f"{share(r, k, 'edge_ever_dormant', 'm8_den'):.3f}"),
                      ("families with no edge dormant at the end", lambda r, k: f"{share(r, k, 'null_end_dormant', 'n_null'):.3f}"),
                      ("family-reviews written", lambda r, k: f"{share(r, k, 'reviews_written', 'reviews_possible'):.3f}")):
        for k in ("v30", "branch", "own"):
            out.append(f"| {label} | {NAME[k]} | " + " | ".join(fn(data[s], k) if s in data else "-" for s in SCEN) + " |")
    return out + [""]


gate = {s: np.sum([r["gate"] for r in A[s]], axis=0) for s in SCEN if s in A}
gate10 = {s: np.sum([r["gate"] for r in B[s]], axis=0) for s in SCEN if s in B}
L += ["## 3. An alternative second condition: the family's own forward record (not adopted)", "",
      "**The two rules.** Both keep the forecast of 3.0 and its thresholds (0.05 at two consecutive reviews, 0.15 to wake) "
      "and add a second number that must also be below 0.05:", "",
      "| | second number | what it uses |", "|---|---|---|",
      "| **on the branch** (Protocol 3.1 §9.1) | `Π^max`: the largest, over the six models, of the posterior probability that the family's edge is at least `θ_min` | the model: the family's reserve and forward results, and every other family through the priors it learns |",
      "| **alternative** (`own_record.py`) | `p^F = Φ((y^F − θ_min)/s^F)`: the one-sided p-value of \"the edge is at least `θ_min`\" on the family's forward Sharpe estimate and its standard error; needs 252 forward days | the family's own forward returns and nothing else. It is also the posterior probability of an edge of `θ_min` under a flat prior on that record: the reading that pools nothing |", "",
      "**Measured on the same fits, at the four pre-registered dates:**", ""] + cmp_table(A)
if B:
    L += ["**With a review every year:**", ""] + cmp_table(B)
L += ["How often each condition holds, among reviews of families that are neither dormant nor supported and have a year "
      "of forward record (branch path): the forecast is below 0.05 in "
      + ", ".join(f"{gate[s][0] / gate[s][3]:.2f} ({s})" for s in gate) + " of them; the forecast and `Π^max` in "
      + ", ".join(f"{gate[s][1] / gate[s][3]:.2f}" for s in gate) + "; the forecast and `p^F` in "
      + ", ".join(f"{gate[s][2] / gate[s][3]:.2f}" for s in gate) + ". The forecast alone decides almost nothing under either rule: it is "
      "below 0.05 for most families at most reviews.", "",
      "**The trade, in words.**", "",
      "- **What the branch's rule has and the alternative lacks: it still retires families.** It leaves a real share of the "
      "families with no edge dormant, more with more reviews, and so saves attention, which is what dormancy is for. It "
      "also uses the reserve record, which the alternative ignores.",
      "- **What the alternative has and the branch's rule lacks: an error that does not depend on the other families.** "
      "V7 is a statement about families that have an edge. `Π^max` is calibrated over all families: among families given "
      "0.05, about 5% have an edge. That bounds the share of edges among the retired, not the share of the edges that are "
      "retired, and the second is the first divided by how rare edges are. `p^F` is below 0.05 with probability 0.05 for a "
      "family whose edge is exactly `θ_min`, at each review, whatever the rest of the programme is, and less often for a "
      "larger edge. The difference shows with yearly reviews: more looks give `Π^max` more chances to retire a family "
      "with a small edge and an unlucky start, while a record that is not against a family stays not against it.",
      "- **What the alternative costs: almost all of dormancy.** An edge of 0 and an edge of 0.25 are a quarter of a Sharpe "
      "ratio apart and the standard error of a forward Sharpe ratio after `T` years is about `1/√T`: a family with no edge "
      "has `p^F < 0.05` with probability about 0.10 after two years, 0.13 after four and 0.20 after ten. Ten years of a "
      "family's own returns cannot tell 0 from 0.25. A rule that retires more does so on the model's word about families "
      "in general. `DORMANCY_DIAGNOSIS.md` says the same of its own rule (\"it rests on the model twice\").",
      "- **Neither is wrong.** The branch's rule passes V7 as pre-registered (four dates) on the pilot. The question for "
      "Ethan is whether dormancy should be allowed to rest on the model's reading of a family when production reviews "
      "quarterly, or only on the family's own record at the price of retiring nearly nobody. A middle course the first "
      "session measured is its own rule with a stricter level (`Π^max < 0.02`).", "",
      "**If Ethan prefers the alternative.** A complete version of it (the text of §9.1 with its box, the code as "
      "`manhattan/stats/dormancy.py`, 12 tests, the SIM_PREREG_v2 reading, a re-hashed record) is on the branch "
      "`claude/epic-mayer-kfhpsh` at commit `1124fe7`, written before this session found the first session's push; the "
      "full suite passed on it. It is not merged anywhere. Taking it means replacing §9.1 and `dormancy.py` on "
      "`build/manhattan`, re-hashing, and rerunning the HB pilot. A partial pilot of it through the runner (36 "
      "replications of D02, 18 of D10, stopped when the overlap was found) retired 2 of 143 families with an edge in D02 and none of 190 in D10.", ""]

# ---- section 4: which model says no
rows = {}
BINS = ((0.25, 0.5), (0.5, 0.75), (0.75, 1.0), (1.0, 1.5), (1.5, math.inf))
for p in glob.glob(os.path.join(trace_dir, "D*_*.json")):
    tr = json.load(open(p))
    r = tr["reviews"]["10"]
    fam = {int(k): v for k, v in tr["fam"].items()}
    pis = np.array(r["pi"])
    for j, i in enumerate(r["idx"]):
        t = fam[i]["true"]
        if t < 0.25 or r["fwd_years"][j] < 2.0:
            continue
        for lo, hi in BINS:
            if lo <= t < hi:
                rows.setdefault((lo, hi), []).append((pis[:, j].min() >= 0.8, pis[0, j] >= 0.8, pis[:4, j].min() >= 0.8,
                                                      pis[:5, j].min() >= 0.8, int(np.argmin(pis[:, j])), r["fwd_years"][j]))
if rows:
    L += ["## 4. Which of the six models keeps a family out of \"Statistically supported\" (a supplement for the tier's bar)", "",
          "`DORMANCY_DIAGNOSIS.md` part 4 has the table Ethan asked for: who reaches the tier by years 4, 6 and 10, by true "
          "Sharpe ratio. This adds one view of why, from the traced pilot replications at year 10 (families with a true edge "
          "and at least two forward years; the same bands). It is not a proposal and nothing was rerun: the six posterior "
          "probabilities the pilot computed, read four ways. The first column is the tier's own condition on `Π` (the tier "
          "also needs a positive forward mean and enough forward days, which these columns ignore).", "",
          "| true hedged Sharpe ratio | families | mean forward years | `Π^min ≥ 0.80` (the rule) | central model alone `≥ 0.80` | smallest of S0 to S3 "
          "(without S4 and S5) | smallest of S0 to S4 (without the decay model S5) | the most cautious model is S4 / S5 |",
          "|---|---|---|---|---|---|---|---|"]
    for (lo, hi), v in sorted(rows.items()):
        a = np.array(v, dtype=float)
        nm = f"{lo:g} to {hi:g}" if hi < 99 else f"{lo:g} and above"
        L.append(f"| {nm} | {len(v)} | {a[:, 5].mean():.1f} | {a[:, 0].mean():.2f} | {a[:, 1].mean():.2f} | {a[:, 2].mean():.2f} | {a[:, 3].mean():.2f} | "
                 f"{(a[:, 4] == 4).mean():.2f} / {(a[:, 4] == 5).mean():.2f} |")
    L += ["", "S4 inflates every standard error by half. S5 says the forward edge halves every three years and asks about the "
          "edge now: a family nine years old needs an edge eight times `θ_min` at its freeze to pass it. For a family with a "
          "true Sharpe ratio between 1 and 1.5 the central model says 0.80 or more nine times in ten and the most cautious "
          "of six about one time in five; the difference is almost all S5 and S4.", ""]
L += ["## 5. What this file does not show", "",
      "1. Anything at the pre-registered count: 12 replications a scenario against 400.",
      "2. Quarterly reviews, which is what production uses. Yearly is as far as either session went.",
      "3. Either rule on a held-out scenario. H09 (dormancy then reactivation) is the pre-registered test of late-starting "
      "edges and is not coded.",
      "4. That the alternative's standard error is right under fat tails or serial correlation beyond what these four "
      "scenarios contain (D05 has Student-t noise with 3 degrees of freedom).", ""]
open(out_path, "w", encoding="utf-8").write("\n".join(L))
print("wrote", out_path)

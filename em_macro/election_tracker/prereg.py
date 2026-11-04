"""Pre-registration documents, docs/elections/<id>.md, written 14 days before each vote.

The document ends with a machine-readable block (```yaml prereg ...```). At results time the
alert reads that block from the last version of the file **committed before the vote day
started** (git history), so a market sign added or changed after the vote cannot be used.
"""
from __future__ import annotations

import datetime as dt
import subprocess

import yaml

from . import snapshots
from .common import DOCS, days_to, load_calendar, load_config, post_issue, today
from .rule import (HOLD_DAYS, KELLY_MULT, PAYOFF_B, RISK_CAP, STOP_K, beta_posterior_mean, kelly_fraction,
                   load_frozen_fit, risk_fraction)
from .rule import ROOT

PREREG_DAYS = 14


def path(eid: str):
    return DOCS / f"{eid}.md"


def _fmt(v, nd=1):
    return "n/a" if v is None or v != v else f"{v:.{nd}f}"


def render(row: dict, c: dict, snap: dict | None, written: dt.datetime) -> str:
    fit = load_frozen_fit()
    p = beta_posterior_mean()
    k = kelly_fraction(p, PAYOFF_B)
    mp = c.get("market_preferred")
    lead = f"{snap['a']} {_fmt(snap['share_a'])}% vs {snap['b']} {_fmt(snap['share_b'])}%" if snap and snap.get("a") else "no usable poll average yet"
    if snap and snap.get("a") and mp:
        cur_sign = {snap["a"]: "+1", snap["b"]: "-1"}.get(mp, "none (market-preferred option is not one of the two leaders: event excluded unless that changes)")
    else:
        cur_sign = "not determined"
    sign_block = (
        f"**Market-preferred side: {mp}.** market_sign = +1 if {mp} is the final-poll leader (a), "
        f"-1 if it is the runner-up (b); on the current average that is **{cur_sign}**. The currency is taken to fear "
        f"the other side.\n\n**Justification (pre-vote analyst coverage).** {c.get('market_sign_justification') or '(missing)'}\n\n"
        + "".join(f"- {s}\n" for s in (c.get("market_sign_sources") or []))
        if mp else
        "**NOT CLASSIFIED.** No market-preferred side has been recorded from pre-vote analyst coverage. Under the "
        "rule the event is **excluded** (no position; the alert is informational) unless the sign is classified "
        "and this file is re-committed before the vote day starts. To classify: set `market_preferred`, "
        "`market_sign_justification` and `market_sign_sources` in `data/elections/tracker.yaml` and run "
        f"`python -m em_macro.election_tracker prereg --id {row['id']} --force`.\n")
    meta = {"prereg": {
        "id": row["id"], "country": row["country"], "currency": row["currency"], "vote_date": row["date"],
        "type": row["type"], "written_utc": written.isoformat(timespec="seconds"),
        "days_before_vote": days_to(row["date"], written.date()),
        "market_preferred": mp, "race_kind": c.get("race_kind"), "options": list((c.get("options") or {}).keys()),
        "poll_snapshot_revid": int(snap["revid"]) if snap else None,
        "current_poll_average": ({"a": snap["a"], "b": snap["b"], "share_a": round(float(snap["share_a"]), 2),
                                  "share_b": round(float(snap["share_b"]), 2), "margin": round(float(snap["margin"]), 2),
                                  "window_days": int(snap["window_days"]), "n_pollsters": int(snap["n_pollsters"])}
                                 if snap and snap.get("a") else None),
        "fit": {"const": fit.const, "slope": fit.slope},
        "rule": {"hold_days": HOLD_DAYS, "kelly_mult": KELLY_MULT, "risk_cap": RISK_CAP, "p": round(p, 6),
                 "payoff_b": PAYOFF_B, "stop_k": STOP_K}}}
    return f"""# Pre-registration: {row['country']} {row['type']} election, {row['date']}

| | |
|---|---|
| id | `{row['id']}` |
| currency | {row['currency']} (vs USD) |
| vote date | {row['date']} ({row['status']}) |
| written | {written:%Y-%m-%d %H:%M} UTC, {days_to(row['date'], written.date())} days before the vote |
| source | {row['source_url']} |

Observation only (paper, size 0). This file fixes, before the vote, everything the results-night alert will use. It must be committed
before the vote day starts; the alert reads the last pre-vote commit of this file.

## 1. Market-relevant quantity

{c.get('quantity') or 'Vote margin (pp) between the two leading options in the final poll average.'}

{('**Not captured:** ' + c['quantity_note']) if c.get('quantity_note') else ''}

Surprise = (actual margin − final poll margin) × market_sign, in pp (docs/elections/ORIGINAL_STUDY.md). The final
poll margin is computed from the last Wikipedia revision of the polling page saved before the vote day starts: the
mean of each pollster's last poll with fieldwork ending in the final 7 days, widened to 10 and then 21 days when
fewer than 2 pollsters qualify; party-commissioned polls excluded; normalisation `{c.get('race_kind')}`.

## 2. Market sign

{sign_block}
## 3. Current poll average

{lead}{f" (pp margin {_fmt(snap['margin'])}; window {int(snap['window_days'])} days; {int(snap['n_pollsters'])} pollsters; Wikipedia revision {int(snap['revid'])}, {snap['rev_timestamp']})" if snap and snap.get('a') else ''}.
This is informational; the surprise uses the final pre-vote snapshot.

## 4. Pre-registered rule (spec section 4.10), observation only

The tracker logs the position below with **size 0, labelled "paper, observation only"**. The rule's own size is
computed only to score the prospective trial (trials.csv T15).

- **Evidence, not a trade:** the day-1 move. Expected day-1 abnormal move = {fit.const:.4f} + {fit.slope:.4f} × surprise
  (% of the {row['currency']} value in USD; frozen 2005–2021 fit, n = {fit.n}, p = {fit.p:.2f}).
- **Entry:** close of the first full trading day after the result.
- **Direction:** sign(surprise); + = long {row['currency']} against USD. Surprise 0 or no market sign: no position.
- **Hold:** {HOLD_DAYS} trading days.
- **Size the rule would take (not traded; logged size 0):** risk = min(0.5 × 0.25 × Kelly(p, b), 2%) of NAV, p = mean of Beta(9, 2) = {p:.3f}, b = {PAYOFF_B:g}
  (assumed; the spec does not give b). Kelly = {k:.3f}, so 0.125 × Kelly = {KELLY_MULT * k:.2%} and the 2% cap binds
  (risk = {risk_fraction(p):.2%}); it binds for any b above about 0.28.
- **Stop:** {STOP_K} × σ_daily × √{HOLD_DAYS}, σ_daily = 60-day half-life EWMA of daily {row['currency']} changes up to
  the entry date. Notional = risk / stop distance.

## 5. Caveats

- The day-1 slope was not significant in-sample (t 1.3, p 0.20); the 0.72 correlation is on 9 hold-out events.
- **Continuation after day 1 is not established.** It was never tested by the study; in the fit sample the
  day-1 → day-5 move went with the surprise in 12 of 26 elections. The tracker exists to test it (trials.csv T15).
- Observation only: every implied position is logged with size 0. No position is taken.

```yaml
{yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()}
```
"""


def write(eid: str, force: bool = False) -> bool:
    cal = load_calendar().set_index("id")
    row = {"id": eid, **cal.loc[eid].to_dict()}
    c = load_config()[eid]
    p = path(eid)
    if p.exists() and not force:
        return False
    if dt.date.fromisoformat(row["date"]) <= today():
        raise RuntimeError(f"{eid}: the vote day has started; a pre-registration can no longer be written")
    snap = snapshots.latest(eid, "weekly")
    if (snap is None or snap.get("ref_date", "") < today().isoformat()) and not snapshots.config_gaps(c):
        snap = snapshots.snapshot(eid, c, row["date"], "weekly")
    DOCS.mkdir(parents=True, exist_ok=True)
    p.write_text(render(row, c, snap, dt.datetime.now(dt.timezone.utc)))
    print(f"wrote {p.relative_to(ROOT)}")
    if not c.get("market_preferred"):
        post_issue(f"[ELECTION-PREREG] {row['country']} {row['date']}: market sign needed",
                   f"`{eid}` votes on {row['date']}. The pre-registration `docs/elections/{eid}.md` was written without "
                   "a market sign, so the event is excluded unless the sign is classified from pre-vote analyst "
                   "coverage and the file is re-committed **before the vote day starts**. See section 2 of the file.",
                   label="election-prereg", dedupe_prefix=f"[ELECTION-PREREG] {row['country']} {row['date']}")
    return True


def due() -> list[str]:
    """Write every pre-registration that is due (scheduled vote within 14 days, none yet)."""
    cal, out = load_calendar(), []
    for _, row in cal.iterrows():
        n = days_to(row["date"])
        if row["status"] == "scheduled" and 0 < n <= PREREG_DAYS and not path(row["id"]).exists():
            if write(row["id"]):
                out.append(row["id"])
    return out


def committed_block(eid: str, cutoff_utc: str, root=ROOT) -> dict | None:
    """The yaml block of the last version of docs/elections/<id>.md committed before `cutoff_utc`
    (committer date, so a back-dated author date does not count)."""
    rel = f"docs/elections/{eid}.md"
    log = subprocess.run(["git", "log", "--format=%H %cI", "--", rel], cwd=root, capture_output=True, text=True).stdout
    cutoff = dt.datetime.fromisoformat(cutoff_utc.replace("Z", "+00:00"))
    sha = next((h for h, t in (ln.split() for ln in log.splitlines() if ln.strip())
                if dt.datetime.fromisoformat(t) < cutoff), None)
    if not sha:
        return None
    text = subprocess.run(["git", "show", f"{sha}:{rel}"], cwd=root, capture_output=True, text=True).stdout
    return parse_block(text) | {"commit": sha}


def parse_block(text: str) -> dict:
    blk = text.split("```yaml", 1)[1].split("```", 1)[0]
    return yaml.safe_load(blk)["prereg"]

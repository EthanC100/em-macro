# Proposal: extending Manhattan's protocol to single technology equities

Version 0.1, 2026-11-18. **A proposal for Ethan's review, not a protocol.** It changes no protected document: Protocol
v3.0.0 and the draft v3.1, SIM_PREREG.md and SIM_PREREG_v2.md are unchanged. Nothing here is adopted or in force, and
no equity hypothesis may be screened, forward-tested or promoted under the existing documents. `manhattan/equities/evidence.py`
refuses it **within this package** (research on non-synthetic sources and every promotion); the protected pipeline
does not yet know about asset classes (section 3).

## 1. Why the existing protocol does not cover equities

1. **Core hedge.** Protocol v3.1 §2.2 hedges each executable on "the core factor returns for the executable's asset
   class: carry, trend, value and buy-and-hold". No daily, point-in-time core factors are defined for single
   equities, and the obvious equity factors (market, sector, size, value, momentum, quality, low volatility) are
   different objects from the macro ones. Without them `X_{x,t}` is undefined for an equity executable.
2. **Simulation coverage.** The simulation pre-registrations test the screening, forward and dormancy rules on
   scenarios built for the existing macro universe. None contains long/short books, borrow costs and recalls,
   delistings, earnings jumps, or cross-sectional strategies over hundreds of names whose returns share one or two
   factors. The rules' error rates there are unmeasured.
3. **Domains and fences.** `config/manhattan.yaml` sets fences per domain; no equity domain exists, and the
   exploration cap (2019-12-31) was set with macro data in mind.
4. **Tail-risk check (§6.11).** The stress loss a family declares is calibrated to macro instruments; single-name
   gaps (accounting fraud, guidance collapses, delisting, squeezes on shorts) need their own stress definition.

## 2. What a future version would need (for Ethan to decide)

| item | proposal | decision owner |
|---|---|---|
| scope sentence | name `us_tech_equities_daily` (and later international) as domains | Ethan |
| equity core factors | daily, PIT, frozen: market (cap-weighted universe), technology sub-industry, size, value, momentum, profitability, investment; each defined from `manhattan.equities.features` primitives on the PIT universe, with returns of tradable long/short portfolios net of a declared cost and borrow | Ethan, after a proposal like CORE_FACTORS_PROPOSAL.md |
| relative-value accounting | a long/short family's return is the book's net return on gross capital, with borrow and financing; directional families on long capital; the two never pooled in one family | Ethan |
| simulation scenarios | add long/short equity worlds: factor-driven cross-sections, borrow fee and recall shocks, delistings with negative outcomes, earnings jumps, crowding unwinds; retest screening FDR, forward e-LOND, dormancy and the tail-risk check on them | a new simulation pre-registration (or an amendment under its own amendment rules) |
| stress loss | per-family declared single-name gap loss (e.g. the short leg's largest plausible gap) feeding §6.11 | Ethan |
| attempt accounting | binding attempt accounting approved before any reserve or forward evaluation | Ethan (session 1's work) |
| reserve | an equity reserve window on the iMac only, set in `config/manhattan.yaml` | Ethan |

## 3. What this PR adds towards it, without changing anything protected

**Not done, and recorded as an owner decision (S8 H3):** scope enforcement in the protected pipeline. Today
`manhattan.ops.promotion.promote`, `manhattan.engine.evaluate` and the runner do not look at a family's domain or
asset class. A future change would make them refuse any domain that the adopted protocol version does not name (and
read `EQUITY_RESEARCH_APPROVED` / `EQUITY_COVERING_PROTOCOLS`, or their successors, from one owner-controlled place).
That touches owner-reviewed code and the protocol; it is Ethan's to authorise and is not done in this PR.


- `evidence.EQUITY_COVERING_PROTOCOLS` (empty) as a second gate on top of `manhattan.ops.promotion`.
- Feature and risk primitives from which equity core factors could be defined.
- Synthetic generators (`manhattan.equities.synthetic`) that a future simulation scenario could build on.
- A catalogue of 39 family drafts that validate against the existing family schema, so nothing about the spec format
  needs to change for equities.

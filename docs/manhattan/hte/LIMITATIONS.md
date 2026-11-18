# Manhattan HTE: scientific limitations, activation blockers and next steps

This engine processes synthetic candidates quickly and keeps complete records. It does **not** produce evidence.
This page says why, what is missing, and what to build next.

## 1. Why nothing here is evidence

1. **The data is synthetic.** Every return comes from `manhattan/hte/data.py`. Its generator is uncalibrated: it uses
   Student-t innovations, GARCH-type volatility and factor structure, with costs invented per domain. A statistic
   computed on it describes the generator. It does not describe any market. When a planted effect is recovered
   (`test_planted_synthetic_effect_is_recoverable_and_labelled_synthetic`), that checks the pipeline, not a discovery.
2. **Every statistic is descriptive.** The stage-2 statistics, stage-3 bootstrap p-values, family SPA and M_eff are
   screening or descriptive quantities. They use a fixed block length and no protocol-designated window, and no
   pre-registration is attached. `CONFIRMATORY` is a constant `False`. Packages carry
   `evidence_class: synthetic_screening_descriptive` and never a count of discoveries.
3. **A candidate is not a hypothesis.** One million candidates here are 5 families, 15 hypotheses and 30 strategy
   specs; the 10^6 run has 256,068 variants. Behavioural classes are fewer than candidates: about 24% of the 10^5
   workload are aliases. M_eff, which is descriptive only, is far smaller again. The engine never turns any of these
   counts into a multiple-testing denominator: `independent_statistical_tests` is `null` (PR #86 owner decision D-1).
4. **Selection after a look is recorded, not corrected.** The engine logs every run, every policy and every post-look
   registration, and it counts repeated looks in the packages. It does **not** adjust any statistic for them. The SPA
   is refused when the variant set is incomplete, but a family that was looked at under several policies still shows
   the latest run's SPA. The look count says how many such runs exist.
5. **Self-review only.** The adversarial pass (ARCHITECTURE.md §8) was done by the author. It does not replace an
   independent reviewer.

## 2. What prevents trustworthy forward evidence

Each of the following would have to be resolved by its owner. None of them can be resolved inside this engine.

| # | blocker | owner |
|---|---|---|
| A1 | Stage 5 is disabled in code (`protected.py`); no caller can enable it | design |
| A2 | PR #86 (binding attempt accounting, sealed PIT windows) is unmerged and dormant; its identity validator has never been run on HTE output | Ethan / PR #86 |
| A3 | PR #86 decisions D-1 (counting unit), D-8 (screening recovery), D-10 (exploration registration) are open | Ethan |
| A4 | no independently retained anchor for the HTE log; a whole-file replacement is undetectable without one | integration |
| A5 | `config/manhattan.yaml`: `reserve.enabled: false`, `claims.enabled: false`, `screening_method: null` (SIM_PREREG_v2 has not chosen the method) | Ethan |
| A6 | no real data path exists by design: no Norgate/Databento loader, no em-macro-data access; the synthetic-only guard refuses anything else | by design |
| A7 | no forward capture: HTE evaluates fixed historical-style windows; it has no daily observation, timestamping or e-process | future work |
| A8 | the HTE methodology (`hte-eval/1`) is not pre-registered: cost model, vol targeting, block length and window are engineering defaults | Ethan, if ever used |
| A9 | cross-platform reproducibility is to rounding only (BLAS); the code identity does not yet pin the BLAS build | engineering |

## 3. Engineering limitations

- **One window.** Every candidate is evaluated on one evaluation window, `[warm-up, fence)`. Multiple windows or a
  walk-forward design would be new attempt kinds.
- **Simple stage-3 model.** Stage 3 uses daily marks and does not model contracts, rolls, ticks or a calendar. PR #85's
  execution layer is the place for that. Wiring it in would cost roughly 100-1000 times more per candidate. Stage 1/2
  bounds would then matter far more, but only sign-blind ones are allowed without a recorded performance gate.
- **The Hölder bound rarely fires.** Under these cost assumptions, stage-1 pruning comes from degenerate candidates and
  aliases. The bound is the tightest sign-blind bound possible (tested), so stronger pruning must use outcome signs,
  which makes it a performance gate.
- **Workers are local.** The engine runs a single-machine `fork` pool (POSIX only) with no distributed scheduler.
  Resume works across machines that share the workspace directory. The workspace `flock` is advisory and local:
  network file systems may not honour it.
- **The disk preflight is coarse.** It allows about 2 KB per candidate, about 3x the measured figure, and it excludes
  the feature cache. Memory is bounded by the sub-batch size but not checked before a run.
- **Stage-4 M_eff uses a subsample.** It is computed on at most `meff_cap` series per hypothesis, chosen by an
  outcome-blind stride, and is labelled as such.
- **The family SPA uses a fixed block length.** It uses `bootstrap_L = 20` and `B = 999` with no B-extension. The
  Protocol's SPA estimates L per family and extends B; that cannot be done in a single streaming pass without storing
  per-variant series.

## 4. What the next engineer should implement (in order)

1. **Wire the identity contract test against PR #86** once it merges: feed `adapters.to_pr86_identity` to
   `ledger.validate_attempt_identity`. Change nothing else until D-1, D-10 and B4 (chunk-to-attempt cardinality) are
   decided.
2. **Add a memory preflight and feature-cache size accounting.** The workspace lock and the disk preflight exist.
3. **Pin the BLAS build in `code_identity()`** (`numpy.show_config`), so that cross-platform reruns are new run
   identities rather than silent tolerance comparisons.
4. **Add a contract-level stage 3 behind the same funnel**, using PR #85 execution once it merges. Run it only on the
   stage-3 representatives, so aliases and degenerate candidates keep their savings.
5. **Add an anchor export.** Write the log head (`AttemptLog.head()`) to the public index or an external timestamp at
   each `run_closed`, as ARCHITECTURE.md §4.1 does for the Manhattan Ledger.
6. **Pre-register any use beyond infrastructure.** If HTE is ever used on exploration data (pre-2020), the methodology,
   the window and the policy must be pre-registered. That is Ethan's decision (CLAUDE.md hard rule 4).

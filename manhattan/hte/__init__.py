"""Manhattan HTE: a high-throughput hypothesis-evaluation engine (research infrastructure, synthetic data only).

Design, integration contract and limitations: docs/manhattan/hte/ARCHITECTURE.md. Benchmarks:
docs/manhattan/hte/BENCHMARKS.md.

Nothing in this package produces evidence. Every number it computes is a *screening* or *descriptive* statistic
on *synthetic* data. Stage 5 (protected evaluation) is disabled in code and cannot be enabled by a caller. The
package reads no real, licensed, reserve or forward data, writes no Manhattan Ledger or Store record, and does not
import the private names of the PR #86 access layer.

    ids         canonical identity: candidate, code, data and run identities
    registry    the immutable candidate registry (families, hypotheses, strategy specs, variants, candidates)
    data        synthetic fenced panels (commodities, rates, FX), the synthetic-only guard
    features    shared, cached rolling features (the main computation reuse)
    templates   signal templates (vectorised position builders) and their parameter schemas
    kernels     stage 1-3 kernels and their plain reference implementations
    policy      the funnel policy (hashed before a run; no performance threshold by default)
    log         the hash-chained, fsynced, append-only attempt log
    store       atomic, hash-verified chunk files
    runner      the staged funnel: scheduling, workers, crash recovery, resume, reconciliation
    package     stage 4 family packages for independent review (descriptive, never confirmatory)
    protected   stage 5: always refuses
    adapters    the boundary to Manhattan attempt accounting (PR #86): disabled
    workload    synthetic benchmark workloads
    bench       the benchmark harness (python -m manhattan.hte.bench)
"""

METHODOLOGY = "hte-eval/1"     # versioned evaluation methodology; part of every candidate identity
EVIDENCE_CLASS = "synthetic_screening_descriptive"
CONFIRMATORY = False           # constant; tests fail if any output claims otherwise

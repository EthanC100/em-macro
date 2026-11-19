"""S16 integration-gap acceptance tests: the joins between the five approved PRs that do not exist yet.

Each test names the component PRs and the integration capability it needs. While the capability is missing the test
is BLOCKED (s16_capabilities.py says why, from the code itself). The moment a probe finds the capability present,
the test FAILS with ``UNBOUND`` and the acceptance criteria below, until it is bound to the adapter's real API. So
flipping a flag can never make the gate pass on its own, and S16 does not guess an API that S11 has not written.

These tests implement no adapter (that is S11's work) and review no merge (S6's).
"""
from __future__ import annotations

import pytest

from s16_helpers import unbound

acc = pytest.mark.acceptance

GAPS = {
    "GAP-01": ("adapter:hte->access", ("hte", "access"),
               "every HTE attempt is registered as a schema-2 attempt in the Manhattan Ledger before it computes "
               "(cardinality per owner decision B4); attempts.reconcile(ledger) is access_reconciled with counts "
               "equal to hte.runner.reconcile; a ledger registration failure leaves no run_closed; HTE identities "
               "keep role exploration, designated False, channel blind; reserve and forward stay unreachable"),
    "GAP-02": ("adapter:hte->execution", ("hte", "execution"),
               "HTE stage-3 representatives execute through manhattan.execution.run with ExecutionPolicy(lag >= 1); "
               "the run identity and every package record the execution timing; no same-close fill remains in any "
               "result used beyond throughput testing; costs and rolls come from a recorded synthetic CostScenario"),
    "GAP-03": ("adapter:hte->evidence", ("hte", "evidence"),
               "every HTE package carries manhattan.evidence metadata and verifier results from a producer in code; "
               "classify gives provenance synthetic, eligibility infrastructure_validation, weight 0 and no grant; "
               "an edited package or an untrusted verifier classifies unverified"),
    "GAP-04": ("adapter:equities->hte", ("hte", "equities"),
               "the synthetic equities world is an HTE domain accepted by a verified-generator check; HTE's PIT "
               "probe covers equity templates; delisting, restatement and as-of guards hold inside HTE runs"),
    "GAP-05": ("anchor:independent", ("access",),
               "attempt-log anchors (Manhattan Ledger and the HTE log) are retained by an independent custodian; "
               "reconcile reports independently_anchored True only against such an anchor and False otherwise"),
    "GAP-06": ("authority:trusted", ("evidence",),
               "a trusted verifier authority exists for spec_registry and synthetic_generator results, with keys "
               "outside this repository; E2E-14 then classifies HTE output synthetic/infrastructure_validation "
               "without any test patching TRUSTED_AUTHORITIES, and every other provenance stays fail-closed"),
    "GAP-07": ("decision:D-1", ("hte", "access"),
               "the multiple-testing counting unit (D-1) is decided and implemented once: HTE package denominators "
               "and attempts.reconcile distinct_specifications count the same unit for the same experiment"),
}


def _case(gid):
    cap, comps, criteria = GAPS[gid]
    return pytest.param(gid, cap, criteria, id=gid,
                        marks=pytest.mark.acceptance(id=gid, area="integration", requires=comps + (cap,)))


@pytest.mark.parametrize("gid,capability,criteria", [_case(g) for g in GAPS])
def test_integration_gap(gid, capability, criteria):
    unbound(capability, criteria)

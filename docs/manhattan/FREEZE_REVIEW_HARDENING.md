# S17 freeze and holdout corrections

The signed tag is resolved once to its immutable object id. Its signed header
must name exactly the requested batch and directly target a commit; its signed
message must contain exactly one `manifest-sha256: <SHA256 of manifest bytes>`
line. Signature verification and manifest lookup then use that same object id.
Aliasing another batch's signed tag cannot authorize a batch in the same commit.
No production key is pinned, and timestamp verification still fails closed.

The current D-6 batch/domain designation can support only one hypothesis per
domain. Preparation refuses ambiguous multi-hypothesis designations. Verification
also resolves executable/variant/hypothesis bindings and refuses legacy ambiguous
manifests before admission or selection. Variants within that one frozen hypothesis
retain the existing registered selection rule. No multiple-testing rule changes.

Selection locks now seal the synthetic world's provenance identity. Holdout calls
check that identity before registering a look. Outside the test-only trust seam,
caller-supplied fences must be verified capabilities. Execution exceptions after
registration record only an execution_error terminal classification, preserve the
designation, and re-raise without logging exception text or performance values.
Successful synthetic reads still have no PIT completion proof and remain explicitly
unfinished; this change does not fabricate a completion.

The static name scan is a heuristic, not an in-process security sandbox. It catches
listed literal names, not arbitrary runtime construction, public-class monkeypatches
or forged exec namespaces. Hostile code running in the trusted Python process is
outside that scan's guarantee. Real research still requires trusted runner custody,
canonical-ledger authority, independent anchors and the existing blinding controls.

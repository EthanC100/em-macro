# Independent workflow baseline: owner decision, not adopted

The workflow hashes in `workflow_baseline_candidate.json` remain an **unadopted
candidate**. This document creates no trusted copy, deploys no verifier and changes
no settings. Workflow pinning and `requirements-manhattan-runner.lock` also remain
unadopted candidates; production research schedules remain disabled.

## Trust requirement

The actor able to change a workflow must not also be able to replace its accepted
baseline, approval record or verifier trust anchor without a separate owner
approval. A checksum proves bytes, not approval. A baseline in the same PR, branch,
repository checkout, Actions artifact or mutable cache does not establish that
independence. Ordinary code commits do not invalidate a workflow baseline; only
the reviewed workflow-byte changes require regeneration.

`manhattan.ops.monitor integrity` compares bytes against a caller-supplied digest
map. It does not authenticate reviews, signatures or baseline provenance. An
independent caller must authenticate the approved copy and execute a trusted
verifier outside the control of the workflows being monitored. A workflow can
otherwise remove its own verification step. Neither independent caller nor
baseline adoption is activated by this engineering PR.

## Storage options

| Location | Conditions and risks | Assessment |
|---|---|---|
| Private `manhattan-ledger` storage | Source-repository sessions must have no access. The runner design gives its deploy key repository write access if provisioned, so a baseline on its ordinary writable branch could be replaced by the same runner. A mirror using equivalent write credentials does not solve this. An owner-controlled protected ref, enforceable against the deploy key, plus an externally pinned/signed approval digest would be needed; repository existence and protection availability must be verified by the owner. Accessing the whole ledger merely to fetch a baseline also exposes private outcomes | Not independently trusted by default. Do not attach or clone the private evidence store for this purpose. Prefer a separate metadata-only trust store; a ledger copy could be an additional witness if independently anchored |
| Protected local Mac account | Owner chooses a non-runner account and directory outside all repository worktrees, worker homes, shared folders and sync/Taildrop destinations. Only that account may approve/update files; the worker must have no write access to files or parent directories. Owner pins/signs the approved digest through a separate channel; a verifier gets only an authenticated read-only copy. Verify actual permissions, backup and account separation locally | Suitable as an owner trust anchor, conditional on local verification. No such account/path/access is assumed to exist or configured here. A verifier running with the approving account's full permissions loses this separation |
| Separate metadata-only owner store | An independently administered repository or immutable artifact store, withheld from source automation's write credentials, with an authenticated approval digest/history. The verifier needs read-only access only to workflow metadata. Availability, retention, account compromise and any cost need owner review | Preferred for an independent remote caller, optionally anchored by a protected Mac/offline copy. No repository, storage service, account or spending is created/authorized by this document |

No option protects against compromise of every approving identity and trust
anchor. Retain historical approvals separately and verify restoration. Do not
store credentials or research outcomes in baseline metadata, and do not expose
private evidence to a workflow-integrity checker.

## Regeneration after workflow pins are approved

These are **future owner actions**, not commands executed in this session.

1. Review the candidate Action SHAs and wheel versions/hashes/provenance and the
   patch's unchanged main-only, environment, permission and dispatch-only gates.
   Have the owner-approved workflow-pin change merged through the normal review
   process. Do not enable the schedule or dispatch the runner to test pinning.
2. Independently record the full approved merge SHA and review/check URLs. Verify
   from the provider that this is the reviewed revision with passing required
   checks. If signed approvals are used, verify their signature against the
   separately trusted owner key. A locally chosen tag or commit author is not
   evidence of approval.
3. In an owner-controlled environment, use a new detached worktree of that exact
   commit. Inspect all workflow additions, deletions and changes since the last
   approved revision. Use the reviewed verifier from this approved checkout,
   never the code from a newly proposed unapproved workflow revision.

   ```bash
   set -euo pipefail
   APPROVED_COMMIT='REPLACE_WITH_FULL_OWNER_VERIFIED_MERGE_SHA'
   REVIEW_DIR=/absolute/owner-private/approved-worktree
   BASELINE_CANDIDATE=/absolute/owner-private/workflow-baseline.candidate.json
   git fetch origin
   git worktree add --detach "$REVIEW_DIR" "$APPROVED_COMMIT"
   cd "$REVIEW_DIR"
   umask 077
   python3 - "$APPROVED_COMMIT" "$BASELINE_CANDIDATE" <<'PY'
   import hashlib, json, re, subprocess, sys
   from pathlib import Path
   from manhattan.ops.monitor import workflow_digests
   approved, output = sys.argv[1], Path(sys.argv[2])
   if not re.fullmatch(r"[0-9a-f]{40}", approved):
       raise SystemExit("full approved SHA required")
   actual = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
   if actual != approved or subprocess.check_output(["git", "status", "--porcelain"], text=True):
       raise SystemExit("approved clean checkout required")
   data = (json.dumps(workflow_digests(Path.cwd()), sort_keys=True, indent=2) + "\n").encode()
   with output.open("xb") as candidate:  # never replace an existing approval
       candidate.write(data)
   print(hashlib.sha256(data).hexdigest())
   PY
   python3 -m manhattan.ops.monitor integrity --root . --approved "$BASELINE_CANDIDATE"
   ```

   Owner-selected directories must already exist with verified access controls.
   Generation writes a **candidate** only. The last command's exit 0 checks
   consistency with the approved checkout, not independence or authorization.
4. Owner reviews the exact candidate diff against the previous trusted map. Record
   the repository identity, approved commit, complete baseline-file SHA-256,
   approval time/reviewer and review/check URLs in a separate authenticated
   approval record. Record the approved lock-file digest separately if it is part
   of the deployment policy: this map covers workflow files only, not all code
   and dependencies. Preserve the previous baseline and approval history.
5. Publish the approved version to the selected independent location using the
   approving identity, not a runner's key. Pin its version/file digest in the
   independent caller's protected configuration. If transport copies it into an
   untrusted workspace, verify that copy against the independently authenticated
   digest before comparison. Never automatically accept a baseline carried by
   the revision currently being checked or refresh it on every ordinary commit.
6. Test acceptance of the approved tree and rejection of a synthetic changed,
   added or deleted workflow, missing/unavailable baseline and altered approval
   digest. Establish external alert delivery and access/backup checks separately.
   Adoption and operational activation still require explicit owner approval.

None of these steps authorizes a research freeze, private evidence access,
production schedule, Mac remote-access change or live workflow dispatch.

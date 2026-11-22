# External ledger anchors in a separately protected repository (design only)

S17, 2026-11-22. Closes finding C5 and owner decision D-7 once adopted. **Nothing here is created or activated**:
no repository, key, token, ruleset, workflow, schedule or code. Creating any of them is the owner's (hard rule 11).

## 1. What an anchor must guarantee

A Manhattan ledger is hash-chained, but its own head proves nothing against the person or process holding the
file. Truncation, a hash-valid rewrite, or two coordinated logs cut back together all verify clean today (C5; the
bridge's F3). An anchor is a statement **outside the ledger holder's control** that "ledger *L* had *n* records
ending in head *h* at time *t*". It must be:

1. **Append-only and immutable** once written: no edit, deletion or force-push, even by the writer.
2. **Writable only by the runner**, never by a Claude session, the night shift or any em-macro workflow.
3. **Independently timestamped**, so that the time is not the writer's own claim.
4. **Outcome-free**: hashes and counts only, so it can be public.
5. **Verifiable offline** by anyone with the ledger and an anchor snapshot.
6. **Fail-closed**: a missing, late or mismatching anchor blocks reports and screening, and never silently passes.

## 2. Repository and permissions

| item | design | owner action |
|---|---|---|
| repository | `EthanC100/manhattan-anchors`, separate from em-macro, em-macro-data and manhattan-ledger. **Public recommended**: anchors are hashes and counts, public history gives third-party visibility, and nothing is lost by publishing them. Private works too, but then only GitHub vouches for its history | create; choose public or private |
| content | `anchors/<ledger_id>.jsonl` (one line per anchor), `proofs/<anchor_hash>.ots` (OpenTimestamps), `keys/allowed_signers` (the runner's SSH signing public keys), `README.md` (this schema). No code, no workflow, no Actions | — |
| writer | **one** deploy key, or a fine-grained token limited to this repository with `contents: write` only, held in the iMac's Keychain by the runner process. Not a GitHub Actions secret; no em-macro workflow can reach it | generate the key; add it as a deploy key with write access |
| readers | anyone (public), or the owner plus a read-only deploy key for verification (private) | — |
| Claude sessions and agents | **no write path.** Not added to the session's GitHub access for this repository, or added read-only. A session can verify, never write | keep it out of `add_repo` write scope |
| ruleset on `main` | block force pushes; block deletions; require linear history; restrict updates to the writer key (bypass list: the deploy key only); require signed commits | apply the ruleset |
| ruleset on tags | `refs/tags/*` cannot be created, updated or deleted except by the owner (monthly roll-up tags, §3) | apply the ruleset |
| admin | the owner only. Admin can override rulesets, so admin actions are themselves recorded (§6) | — |
| CODEOWNERS (em-macro) | the future verifier code (`manhattan/anchors/*.py`) and its tests are added to the protected block | edit CODEOWNERS |
| hard rule 16 | no workflow writes anchors. If one is ever proposed, it joins the writer list | — |

## 3. Anchor record and immutable references

One JSON line per anchor, canonical form (sorted keys, no spaces, the `ledger.record_line` escaping):

```
{"schema": "manhattan.anchor/1",
 "ledger_id": "<sha256 of the ledger's first record line>",   # stable across copies and paths
 "records": 1234, "head": "<hex>",                             # the ledger state anchored
 "event": "run_close" | "batch_freeze" | "heartbeat" | "key_rotation" | "incident",
 "run_id": "<hte or runner run id | null>", "code_commit": "<em-macro commit>",
 "utc": "2027-01-15T22:41:07Z",
 "prev_anchor": "<sha256 of the previous anchor line for this ledger_id | genesis>",
 "signer": "<ssh key fingerprint>", "sig": "<ssh signature over the line without sig>"}
```

**Immutable reference** for an anchor = `(repository, commit SHA, path, line number, anchor hash, OTS proof)`.

- The anchors for one ledger are themselves hash-chained (`prev_anchor`), so removing a middle anchor breaks the
  chain even before git history is consulted.
- Each anchor's hash is stamped with OpenTimestamps (Bitcoin attestation). The `.ots` proof is upgraded once
  confirmed and committed under `proofs/`.
- Monthly, the owner tags the anchors repository (`anchors-YYYY-MM`) and records the tag's commit SHA in a
  hash-only line in em-macro (a later owner decision; it gives a second, independent custody point).

## 4. When anchors are written

| event | content | blocks until written |
|---|---|---|
| `batch_freeze` | the ledger state just after the `batch_freeze` record | any evaluation of that batch |
| `run_close` | after the run's last terminal record, **before any result is read, reported or published** | the run's report and any screening use |
| `heartbeat` | every 24 hours during a long run | nothing; it narrows the unanchored window |
| `key_rotation`, `incident` | §6 | — |

## 5. Verification (what `reconcile` would do)

```
latest = last anchor for ledger_id, after verifying the signature chain, the prev_anchor chain and git history (no force-push)
require ledger.records >= latest.records                      # truncation below an anchor: refused
require hash(record[latest.records - 1]) == latest.head       # a rewritten prefix: refused
for every earlier anchor a: require hash(record[a.records - 1]) == a.head      # the whole anchored history
tail = records after latest.records                          # unanchored: allowed only for an open run
independently_anchored = all of the above and no closed run lies in the tail
```

- The verifier reads an anchors snapshot (a clone or archive at a named commit), so verification never needs
  network access or write rights.
- `attempts.reconcile` reports `independently_anchored: True` only from this function; today it is a constant
  `False`.

## 6. Failure behaviour and recovery

| situation | behaviour (fail closed) | recovery procedure |
|---|---|---|
| anchor push fails (network, authentication, rejected) | the run stays **unanchored**: its report builder and every screening step refuse; the ledger keeps accepting terminal records; no new run starts on that ledger after 24 hours unanchored | the runner retries with backoff; the owner runs `anchors push --pending` by hand. The anchor carries the original close state, and its `utc` shows the delay |
| an anchor does **not** match the ledger | **integrity incident**: the ledger is opened read-only, every run on it is blocked, and the owner is alerted. No automatic repair | the owner compares the backups, the anchors and git history; writes an `incident` anchor describing the finding; any attempts proven by an anchor but missing from the ledger count in every denominator as failed-after-read (conservative); the ledger is never "fixed" to match |
| local ledger lost (disk failure) | as above | restore from backup and verify against the anchors. Records after the backup's last anchor are lost and recorded as an incident; the anchored count still binds the denominator |
| legacy raw-separator ledger (pre-#104) | verification refuses (it cannot be read) | PR #104 option B: an owner-run re-escape copy. Record hashes are unchanged, so existing anchors still match |
| writer key leaked | anything signed after the leak time is suspect | revoke the deploy key; generate a new one; write a `key_rotation` anchor signed by the owner's key naming the old and new fingerprints; OTS proofs still bind every earlier anchor to its time |
| anchors repository deleted or rewritten by admin | detected by the `prev_anchor` chain and OTS proofs against any earlier snapshot | restore from the monthly tag recorded in em-macro, or from any verifier's snapshot; record an `incident` |
| GitHub unavailable | as "push fails" | as above. OTS stamping can proceed offline and the commit later |

## 7. Tests to write with the implementation (synthetic; a local bare repository stands in for GitHub)

- Truncation by every k ≥ 1 below the latest anchor is detected.
- A hash-valid rewrite of an anchored prefix is detected.
- An unanchored closed run blocks the report.
- A missing middle anchor breaks `prev_anchor`.
- A bad signature or an unknown signer is refused.
- A force-pushed anchors history is detected against an earlier snapshot.
- A push failure leaves the run unanchored and the report builder refuses.
- Recovery after a retry leaves the run anchored.
- The verifier runs with no network access.

## 8. What the owner decides

1. Create the repository: public (recommended) or private.
2. Generate the writer key and hold it on the iMac only.
3. Apply both rulesets.
4. Approve OpenTimestamps as the time source (free; no account).
5. Approve the 24-hour unanchored limit.
6. Approve the monthly roll-up line in em-macro (optional, later).

Until then, `independently_anchored` stays `False`, and nothing that depends on it (screening, First Light's FL-4)
can pass.

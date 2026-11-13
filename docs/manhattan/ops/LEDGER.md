# The private ledger (`manhattan-ledger`)

Code: `manhattan/ops/store.py`. Tests: `tests/test_manhattan_ops_store.py`, `tests/test_manhattan_ops_e2e.py`.

Runner storage on GitHub Actions disappears when the job ends. It is never the only record: every write is pushed to
a private git repository before the run moves on, and mirrored after the run.

## Layout

```
chain.jsonl        append-only, hash-chained records (every type)
journal.jsonl      write-ahead journal: pending -> committed -> verified
raw/<sha256>.bin   first-seen captures of source data (content-addressed)
logs/<run>.log     each run's private log
heartbeat.json     a copy of the last heartbeat (the chain record is authoritative)
```

## Records

`seq, ts_utc, type, key, nonce, provenance{source, retrieved_utc, run_id, run_attempt, commit}, payload, prev_hash,
hash`. The hash is the SHA-256 of the canonical form (`manhattan.spec.canonical_bytes`) of every other field. The
nonce is 128 random bits. Types: `lock`, `unlock`, `lock_broken`, `capture`, `capture_failed`, `registration`,
`screening`, `observation`, `missed_observation`, `missed_run`, `heartbeat`, `conflict`.

| property | how |
|---|---|
| append-only, tamper-evident | every hash is recomputed when the ledger is opened; an edited, removed or reordered record stops the run |
| idempotent | a key is unique: `("observation", prediction, date)`, `("capture", source, sha256)`, `("registration", prediction, status)`, `("heartbeat", date)`, and so on. The same content again is a no-op; different content is refused and recorded as a `conflict`; the first record stands |
| atomic | a rejected (non-fast-forward) push makes the runner fetch, reset its clone to the remote and re-append its records; duplicates fall away by key. The code never force-pushes (a test reads the source) |
| partial jobs | a write goes `pending` (pushed with the intended records) -> `committed` (records and journal line pushed together) -> `verified` (re-read from a fresh fetch). Each run starts by finishing every unfinished entry |
| concurrency | the workflow's concurrency group, then a `lock` record pushed before anything else (git's fast-forward rule makes it a compare-and-swap). A live lock of another run stops the run; an expired lock (75 minutes) or an earlier attempt of the same run is broken with a `lock_broken` record |
| missed days | a weekday without a completed run becomes `missed_run`; data not available by the source's grace period become `missed_observation`; data that arrive after a gap are recorded `reconstructed` with weight 0. Never success |
| provenance | every record carries its data source, retrieval time, run id and attempt, and the em-macro commit |

**Crash tests.** A run is killed at each of nine stages (after the lock, after the local journal write, after the
journal push, half-way through writing the chain file, after the local commit, after the push, after verification,
half-way through the mirror push, before the unlock). After each, a fresh run recovers, and the final ledger has the
same keys and content as a run that never crashed: nothing duplicated, nothing missing, every earlier record
byte-identical, chain and mirror verified.

## Mirror

After each run the runner pushes the ledger to a mirror by fast-forward only, then clones the mirror and recomputes
both chains: `equal`, `behind` (a prefix: lagging), or `diverged`/`broken` (tampering). A rejected mirror push is
reported, never forced. Options for Ethan (the workflow reads `vars.MANHATTAN_MIRROR_URL`,
`vars.MANHATTAN_MIRROR_HOST`, `vars.MANHATTAN_MIRROR_KNOWN_HOSTS` and the secret `MANHATTAN_MIRROR_DEPLOY_KEY`):

| option | cost | independence | note |
|---|---|---|---|
| **A. a private repository on another provider** (Codeberg, GitLab.com) with its own deploy key | free | different company and infrastructure | **recommended** for the push mirror |
| B. the iMac pulls nightly (`git fetch` by launchd with a read-only deploy key) | free | Ethan's own hardware; no secret in Actions | **recommended in addition**: a copy no cloud account can delete |
| C. a second private GitHub repository under another account | free | same provider | protects against a deleted repository, not against GitHub |
| D. object storage with a retention lock (S3 Object Lock, Backblaze B2) | spending | strongest: the copy cannot be rewritten for the retention period | needs a small script; spending is Ethan's |

## Tamper evidence without branch protection

GitHub Free has no branch protection or rulesets on private repositories (they need Pro, Team or Enterprise), so the
deploy key could rewrite `manhattan-ledger`'s history. Tamper evidence then rests on:

1. the hash chain (any edit breaks it, and the runner refuses a ledger that does not verify);
2. the head hash published in every run's public health record (Actions logs of a public repository are kept for
   at most 90 days, so this anchor is short-lived; the mirror and timestamps are the lasting ones);
3. the mirror, verified record by record after every run;
4. optionally, an OpenTimestamps stamp of the head after each run (not built; the `ots` client is free).

With GitHub Pro, add a ruleset on `manhattan-ledger`'s `main`: block force pushes and deletions.

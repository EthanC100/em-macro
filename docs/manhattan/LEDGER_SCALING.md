# Manhattan ledger scaling (phase 3)

The HTE attempt bridge (PR #98) put PR #86's ledger under a load it had not met: one attempt per candidate,
100,000 candidates per run. Accounting cost 26 minutes against 44 seconds of HTE computation. On the indexed ledger
the same run spends 2.4 minutes on accounting. This change makes the ledger, the strict reconciler and the fence
check scale roughly linearly. It changes **no rule, record or answer**. It touches no protected path, owner policy
or scientific counting rule, and it does not activate the bridge.

Every number below is synthetic infrastructure measurement (`scripts/ledger_scale_bench.py`; results and hardware
in `results/manhattan_ledger_scaling/`). None of it is evidence.

## 1. Where the time and memory went (main, 5e4765e)

Each phase was profiled separately on an HTE-shaped workload. Each candidate has one schema-2 attempt on an
8.8-year exploration window. 1 in 97 candidates fails; 1 in 53 is evaluated twice (a rerun).

| phase | cost on main | cause |
|---|---|---|
| registration (`access.register_evaluation`) | ~2.5 ms per candidate, linear | `roles.check_read` walks every day of the window in Python (3,200 calls of `role_of`), about 80% of the time. The rest is `fsync` and canonical hashing. |
| completion (`Ledger.record_evaluation`) | **quadratic**: 1,084 s at 100k in the bridge | the `data_changed` rule scans every earlier evaluation (`earlier = [r for r in self._evals ...]`) |
| strict reconciler (`attempts.reconcile`) | ~2 ms per attempt | `access.check_recorded` re-runs the same per-day `check_read` for every start |
| opening a ledger | linear, twice | `verify` parses and hashes the file, then `read` parses it again |
| memory | ~7.8 kB per record (~16 kB per candidate) | every record held as parsed objects, about 5× its JSON. The reconciler holds every record of the snapshot as objects too. |

## 2. Three ways out

| | indexed ledger (this change) | one ledger per run | ledgers partitioned by identity (`spec_hash` prefix) |
|---|---|---|---|
| completion cost | O(1) per completion | O(run size) per completion: quadratic within a run | O(n / shards) per completion: still quadratic, divided |
| registration and reconciler | the fence decision is remembered (§3.3) | unchanged (~2.5 ms + ~2 ms) | unchanged |
| memory | records held as their JSON lines (~2.2 kB per record) | unchanged per record; less only if old ledgers are closed | unchanged per record |
| rerun and nondeterminism detection | unchanged: one ledger, one key space | **lost across runs**: a rerun in a later run's ledger is a new look, and a conflicting result is not seen | kept: the key `(spec_hash, data_hash, window)` and the `data_changed` rule `(spec_hash, window)` stay inside one shard |
| designated-reserve uniqueness (D-6, `(batch, domain)`) | unchanged | lost across runs | **lost**: a batch's attempts spread over shards, so the one-designated check needs every shard |
| anchors (D-7) | one head | one per run | one per shard; a shard can be withheld without breaking any chain |
| looks summed over ledgers (measured, 100k) | equal to the distinct keys | **over-counts** the reruns that landed in a later run's ledger | equal to the distinct keys |

The indexed ledger is the only one that keeps every rule. The measured comparison is in §5.

## 3. What changed

### 3.1 `manhattan/ledger.py`: the indexed ledger

- **Records are held as their verified JSON lines** (the bytes in the file), not as parsed objects. They are decoded
  when read. `records()` and `records(type)` return what they returned before; `iter_records()` streams them.
- **Every whole-ledger scan is an index**:
  - the `data_changed` rule's earlier evaluations of a spec on a window, and the result of record: `(spec_hash, window id)` → `(seq, position, designated)`;
  - suspended families: a set;
  - records of a type: position lists.
  
  The Phase 4B indexes (starts, terminals, supersessions, keys, legacy completions, designated reserve starts)
  remain. They now hold sequence numbers and shared identifier strings instead of records.
- **Opening verifies and indexes in one streamed pass** (`iter_verified`), one line at a time. That pass covers only
  the regular case:
  - valid UTF-8;
  - one record per `\n` line;
  - every record valid.
  
  Anything else raises `IrregularSnapshot`, and the ledger then uses the original path, `verify_snapshot`, on the same
  bytes. It therefore accepts exactly what main accepts and refuses with the same message. Opening also no longer
  reads the file twice. On main, `verify` and `read` were two reads, so the records indexed could differ from the
  records verified.

### 3.2 `manhattan/attempts.py`: the streamed reconciler

`reconcile` checks the snapshot line by line, checks that it reaches its anchor, then parses the records up to the
anchor one at a time for the unchanged `_ledger_pass`. That pass keeps each start's payload as compact JSON until the
end. Irregular snapshots take the original path. The report is identical to main's (tested).

### 3.3 `manhattan/access.py`: remembered fence decisions

`roles.check_read` is a pure function of its arguments. `access._allowed_role` remembers its *allowed*, token-free
decisions in a bounded table. The decision is never changed; only its repetition is saved.

**What is remembered.** Only an allowed read without a token, with inputs of exact built-in types:
- `str` caller, domain and window ID;
- `date` dates, never a subclass;
- a `bool` enabled flag and an `int` holding;
- the domain's reserve window either absent or a 2-tuple of `date`.

Everything else is decided by `check_read` itself, every time: a refusal, a reserve read (a token), a fence that is
not a `roles.Fence`, other types, and anything whose key cannot be built.

**What the key holds.** Exactly what `check_read` reads:
- the caller, the window, the freeze and the holding;
- from the fence, only `exploration_end`, `enabled` and *this domain's* reserve window (`role_of` reads
  `fence.reserve.get(domain)` and nothing else of the reserve);
- the identity of `check_read`, `role_of`, `_busdays_between` and `_day`;
- the values of the `roles` settings they read.

**Where the decision is made.** On a snapshot fence built from the key's own values, so a reserve mapping changed
mid-call cannot store one content's answer under another content's key.

**Independent review (PR #100, 20 November 2026).** The first version keyed the fence by its JSON text. A security
review found that this let a fence whose reserve is keyed by the integer `1` (which `yaml.safe_load` can produce)
store an allowed decision. The reconciler then accepted a recorded reserve window on the domain `"1"`. The review also
found four hardening gaps:
- extra window elements;
- lying `date` subclasses;
- tightened `roles` settings;
- a mid-call mutation race.

The rules above close all five. Each finding has a regression test that fails on the first version.

`roles.py` is not changed.

## 4. What is preserved, and how it is tested

`tests/test_manhattan_ledger_scaling.py` (57 tests) runs the current modules beside **reference copies of main's
`ledger.py` and `attempts.py`** (`tests/manhattan_*_reference.py`, unchanged except for their imports).

- **Same files, records, answers and reports.** Random lifecycles across 12 seeds × 160 steps cover:
  - schema-2 and legacy starts, retries, completions with and without attempt IDs;
  - reruns, nondeterminism and `data_changed`;
  - failed and aborted terminals, corrections and refused calls.
  
  The tests require all of the following:
  - byte-identical ledger files;
  - the same return value or the same error for every call;
  - the same answer to every query, every 20 steps, after reopening, and with each implementation reading the other's file;
  - indexes rebuilt from the file equal to the indexes kept in step;
  - the same reconciler report at five anchors, unscoped and scoped to two batches.
  
  A coverage test checks that these lifecycles reach every outcome. Mutation checks confirmed that the
  differential fails when the index picks the wrong first result, the wrong result of record or the wrong
  supersession, or when the reconciler audits past its anchor or ignores its batch scope.
- **Append-only history and tamper detection.** Each of the following is refused or reported exactly as on main:
  - edited, dropped, swapped or truncated records;
  - invalid UTF-8, appended garbage, an unknown type;
  - a chain rewritten with valid hashes (refused at its anchor).
  
  A stale ledger object appending on an old head forks the chain, and the fork is refused on reopening.
- **Indexing cannot hide conflicts or forgeries:**
  - a conflicting result is always a nondeterminism, before and after reopening;
  - a completion written around the index by another writer is decided on reopening and reported by the reconciler;
  - forged escalated starts, foreign completions, unknown attempts, double terminals and identity mismatches are each reported, with reports identical to main's.
- **Every candidate keeps its own auditable identity and outcome:** one start and one terminal per attempt, found by
  attempt ID, with batch-scoped counts.
- **Irregular files** (CRLF, blank or NBSP lines, BOM, no final newline, U+2028 inside a string) take the reference path,
  with identical results.
- **The fence memo:** 1,600 random fences, windows, callers, freezes and holdings give the same result as
  `check_read`, including the error. A fence whose content changes is decided anew, and a replaced `check_read` is
  never bypassed. Refusals and reserve reads are never remembered.

### Deliberate differences

- `records()` returns new objects on every call. On main it returned the ledger's own objects, so a caller that
  mutated one changed the ledger's view of itself. Records appended in a session now have sorted keys, as they always
  did after reopening.
- A malformed evaluation can only be written by a forged write (no spec hash, no window ID, no designation, or a
  nondeterminism without a family). On main the scan raised `KeyError` or `TypeError` on such a record. The index
  raises `LedgerError` at the same rule. `result_of_record` now refuses even where main's scan might have returned
  an earlier match. Both fail closed (tested).

## 5. Benchmarks

See `results/manhattan_ledger_scaling/README.md` for the full tables. Summary (single ledger, 4-CPU Xeon):

| ledger | candidates | accounting s (register / complete / reconcile) | µs per candidate | ledger memory per candidate | looks summed / keys |
|---|---|---|---|---|---|
| main | 10,000 | 60.6 (26.0 / 12.7 / 22.0) | 6,059 | 15.8 kB | 9,896 / 9,896 |
| indexed | 10,000 | 8.9 (4.0 / 3.4 / 1.4) | 887 | 4.5 kB | 9,896 / 9,896 |
| main | 100,000 | 1,481.9 (258.1 / 1,007.3 / 216.5) | 14,819 | 15.7 kB | 98,969 / 98,969 |
| main, one ledger per 10k run | 100,000 | 601.3 (252.1 / 131.6 / 217.6) | 6,013 | 13.7 kB | **100,650** / 98,969 |
| main, 16 `spec_hash` shards | 100,000 | 736.9 (261.2 / 263.1 / 212.6) | 7,369 | 13.5 kB | 98,969 / 98,969 |
| indexed | 100,000 | **90.1** (43.4 / 35.1 / 11.6) | 901 | 4.5 kB | 98,969 / 98,969 |
| indexed | 1,000,000 | 844.5 (394.2 / 334.6 / 115.8) | 845 | 4.5 kB | 989,690 / 989,690 |

- **Scaling.** The indexed ledger is linear: 887, 901 and 845 µs per candidate at 10k, 100k and 1M. At 100k it is
  16× faster than main, with 3.5× less ledger memory.
- **Main at 1M** was not run. Its completion is quadratic (about 28 hours extrapolated), and its ledger would need about
  15 GiB.
- **End to end**, PR #98's bridge at 100k spends 142 s on accounting (3.0× the HTE run) on the indexed ledger, against
  1,569 s (35.6×) on main.
- **Alternatives.** One ledger per run is the cheapest alternative, but it counted 1,681 reruns as new looks and no
  reconciler noticed.

## 6. Remaining blockers and owner decisions

1. **Main's capability scan fails before this change.** `tests/test_manhattan_binding_access.py::test_private_access_paths_are_used_only_where_allowed`
   fails on main 5e4765e: `manhattan/marketdata/continuous.py` uses `Window` and
   `manhattan/marketdata/adapters/fixture.py` uses `_value`, and neither module is on the allowlist. The allowlist is
   a reviewable access decision, so this change does not touch it.
2. **A pre-existing PR #86 defect: some characters make a ledger unopenable.** `verify_snapshot` splits the file
   with `str.splitlines()`, which also breaks at U+2028, U+2029, U+0085 and other separators. `json.dumps(...,
   ensure_ascii=False)` writes those characters unescaped, so a payload string containing one makes the ledger fail
   verification on reopening. Everything that can append a free-text string can trigger it: `Ledger.append`,
   correction reasons, completion summaries. After that, neither the ledger nor the strict reconciler can read the file.

   This change leaves the defect exactly as on main. For each of the three characters,
   `test_the_known_line_separator_defect_is_unchanged_not_worse` checks that both implementations:
   - write the same bytes;
   - refuse to reopen with the same message;
   - give the same reconciler error and the same `verify` result.

   **Recommendation: fix it separately, as a change to PR #86's file format.** The smallest fix is on the writer side:
   escape these three characters in the written line. The record hash is computed over the parsed record, so escaped
   and raw lines hash the same, existing valid ledgers stay valid, and `verify` is untouched. Ledgers already written
   with a raw separator would still need a reader that splits on `\n` only. That is the riskier half, because it
   changes what `verify` accepts, so it is an owner decision.
3. **`fsync` per record is now the largest write cost** (~0.23 ms here, about half of registration). It is PR #86's
   durability rule: a registration that returned survives a crash. Group commit would need a batch registration API
   that returns no context before its batch is `fsync`ed. That is an owner decision.
4. **Canonical hashing** (`spec._canon`, ~0.1 ms per record, twice per write and once per verification) is what the
   record hash is defined over. It is unchanged.
5. **Memory is still held in memory**, at ~2.2 kB per record. Beyond about ten million records, an index of file
   offsets with a per-record digest (re-read and checked on access) would bound it. That change is not made here.
6. **The fence memo is in `access.py`**, the authorization module. An independent security review found one
   cache disagreement, now fixed (§3.3), and four hardening gaps, now closed. It still needs its owner's review.
   Related but older than this change: `roles.Fence.from_config` silently ignores a reserve keyed by a non-string
   (`1:` in YAML), with or without the cache. It should reject such keys; that is a change to `roles.py` and
   needs its owner.
7. **PR #98**, the bridge, still needs D-10, D-1, B4 and A-1–A-3. Its `_batch_state` and `crosscheck` read
   `ledger.records()` whole. That is fine at 100k; at 1M they should use `iter_records`.

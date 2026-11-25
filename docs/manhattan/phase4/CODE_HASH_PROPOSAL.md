# The simulation code hash: what it covers today, and a narrower design for future runs

A proposal for the owner, from the S6 follow-up of PR #83. **Nothing here is implemented.**

- `manhattan/sim/run.py` is not changed.
- No record's identity is recomputed.
- No old result becomes valid.

## 1. What the hash covers today

`run.code_hash(size, version)` (`manhattan/sim/run.py:81`) is a SHA-256 over the path and bytes of a fixed list of
files. A record carries the first 16 hex digits as `code`. The HB list for version 2 is `CODE_FILES_V2_HB`
(`run.py:62`).

| check (deterministic, read-only) | finding |
|---|---|
| **Too broad.** Does the HB hash include code that cannot change a simulation number? | **Yes.** It hashes all of `manhattan/ledger.py`: 343 lines, 11 top-level functions and classes, the operational ledger. The model uses one function from it, `evidential_weight` (`manhattan/stats/hier_analytic.py:61,178`), called with `reconstructed` left at False. Three operational commits after run `43467828524` (`436b9fd`, `135a035`, `2e54231`) changed the file, and the HB hash went from `4252b971831004e3` to `c864e57955126c37`. |
| Did any of those changes alter what the model computes? | No. The only change to `evidential_weight` is `and not reconstructed` on the reserve branch, which is inert for the model's call (`tests/test_manhattan_sim_readiness.py::test_the_model_reads_evidential_weight_with_its_default_reconstructed_flag`). This is a fact about the code. **It does not make the old records valid** (section 3). |
| **Too narrow.** Are there modules the hashed code imports that are not hashed? | **Yes**, by a static import-closure walk over the hashed files, within the `manhattan` package. Besides `manhattan/__init__.py` and `manhattan/stats/__init__.py`, unhashed imports are: `manhattan/prereg.py` for every route (used by `seeds.prereg_hash`), and for version 2 at HB, also `manhattan/spec.py` and `manhattan/availability.py` (imported by `ledger.py`) and `manhattan/stats/hier.py` (imported by `hb.py`). The walk checks imports only; whether a number depends on these is not shown. |
| STD and LONG routes, versions 1 and 2 | No ledger file; the only unhashed import is `manhattan/prereg.py`. |

So the current scheme ties simulation identity to operational edits it does not depend on, and does not tie it to
some modules it does import.

## 2. Proposed design: "code scheme 2", for future runs only

1. **Simulation-only sources stay whole-file hashed.** These are the stats and sim modules that exist only for the
   simulation: the lists of today minus `manhattan/ledger.py`.
2. **Shared modules are hashed by function, from a manifest.** A frozen manifest names each object the simulation
   imports from a shared module, for example `manhattan.ledger:evidential_weight` and `manhattan.ledger:LedgerError`.
   The hash covers the normalised source of exactly those objects (`ast.get_source_segment` of each definition, with
   a version tag), plus the manifest itself.
3. **A closure test makes the manifest complete.** It walks the imports of the hashed files and fails if any
   `manhattan` module or name outside the hashed set and the manifest is imported. This closes the "too narrow" side
   (`prereg.py`, `spec.py`, `availability.py`, `hier.py`): each is then either hashed or explicitly declared inert
   with a reason.
4. **An optional behavioural fingerprint.** For small pure functions such as `evidential_weight`, add their output
   on the full input domain (a truth table) to the hash. A refactor that keeps behaviour then keeps identity, and a
   behaviour change always changes it.
5. **Identities are labelled by scheme.** New records carry `code_scheme: 2` beside `code`. Records without the field
   are scheme 1.
6. **Scheme 2 must not touch earlier records.**
   - Scheme 1 identities are never recomputed or rewritten.
   - `collect`, `report`, `report_v2` and `dev_status` compare a record only with the current code's identity under
     **that record's own scheme**.
   - A scheme-1 record is countable only if the current checkout's scheme-1 hash equals it, exactly as today.
   - A scheme-2 identity is never computed for an old record, so no old record can match a scheme-2 hash.

## 3. Why this does not validate the old HB records

The proposal changes nothing about records already made. The records of run `43467828524` keep
`code = 4252b971831004e3` under scheme 1. Main's scheme-1 HB hash is `c864e57955126c37`, so they stay "other code"
and stay uncountable.

There are two ways forward, and both belong to the owner:

- **(a) Re-run the five HB runs** under the current code, or under scheme 2 once it is adopted: about 520 CPU-hours.
- **(b) A written ruling** under SIM_PREREG_v2 §9 that this particular difference is not "different code". This is
  decision D1 in SIMULATION_READINESS.md: a reading of a frozen rule, for the owner, recorded before it is used.

Scheme 2 is neither of these, and it must not be used to argue (b).

## 4. What adopting scheme 2 would need

- **The owner's go-ahead.** `run.py` is not in any code hash, but SIM_PREREG_v2 §9 ("each carries the hash of the
  code that made it") is frozen text. A different hashing scheme is a reading of it, and should be recorded in
  `docs/manhattan/SIM_PREREG_AMENDMENTS.md` or in the next version, before any run uses it.
- **Changes to the runner and the readers:**
  - `run.code_hash` gains a `scheme` argument;
  - records carry `code_scheme`;
  - `collect.merge`, `run.load_reps` and the reports compare per scheme;
  - tests prove that scheme-1 hashes of today's checkout are byte-for-byte unchanged, and that the closure test
    passes.
- **New runs.** Runs made after adoption start from zero under scheme 2. No earlier record moves.

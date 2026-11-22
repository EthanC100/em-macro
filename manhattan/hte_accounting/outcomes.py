"""Per-candidate outcomes of an HTE run: deterministic result hashes and batched storage (at most 512 per file).

**Two hashes per candidate.** An HTE candidate's row in the results of record holds two kinds of value:

* *intrinsic*: a function of the candidate's executable, the data and the window alone. These are the stage-1 and
  stage-2 statuses and statistics, the behavioural fingerprint, the stage-3 statistics except the bootstrap p-value,
  and the hash of the stage-3 return series. An exact behavioural alias's stage-3 values are copies of its
  representative's, which are bit-identical to its own by construction (PR #89 ``test_alias_results_equal_direct_
  computation``). So an alias's intrinsic stage-3 status is its representative's ("computed", or "failed" with the
  representative's reason), not "alias".
* *cohort-dependent*: values that also depend on which other candidates are in the run. These are the funnel
  disposition (computed vs alias), the alias representative, the cross-family behaviour flag, and the bootstrap
  p-value. ``kernels.stage3_boot`` documents that a matrix product's per-column bits depend on the other columns of
  its 64-candidate group.

``result_hash`` covers the intrinsic values and is what PR #86 compares (``Ledger.record_evaluation``: the same
executable on the same data and window must give the same ``result_hash``, else ``nondeterminism``). Registering an
unrelated candidate, or changing who represents an alias class, therefore never fakes a nondeterminism.
``cohort_hash`` covers the cohort-dependent values. It is stored beside ``result_hash`` in the outcome batch and in
the completion's summary, so nothing in the row escapes hashing. The cohort itself is pinned by the HTE run identity
(registry root, policy), which is the PR #86 ``batch`` (``hte-<run id>``).

**Batches.** Rows are stored in canonical order in files of at most ``BATCH_MAX`` candidates, written with
``manhattan.hte.store`` (atomic, SHA-256 named in the record). Each file holds every column, both hashes, the
candidate, executable and PR #86 attempt digests, and each row's terminal. Any row can be verified alone:
``verify_batch`` recomputes every row hash from the stored columns.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

from manhattan.hte import kernels, store
from manhattan.hte.runner import S3

BATCH_MAX = 512
SCHEMA = "manhattan.hte_accounting.outcomes/1"
RESULT_DOMAIN = b"manhattan.hte_accounting/result/v1\0"
COHORT_DOMAIN = b"manhattan.hte_accounting/cohort/v1\0"
TERMINAL = {"completed": 0, "failed": 1}
_P = kernels.S3_COLS.index("p_boot")
# fixed little-endian dtypes: the hashes do not depend on the platform's native byte order
_DT = {"s1": "<u1", "reason1": "<u1", "stats2": "<f8", "fingerprint": "<u1", "s3": "<u1", "reason3": "<u1",
       "stats3": "<f8", "series_sha256": "<u1", "s3_disposition": "<u1", "alias_rep": "<u1",
       "cross_family_behaviour": "<u1", "p_boot": "<f8"}


class OutcomeError(RuntimeError):
    pass


def intrinsic_columns(table: dict) -> dict:
    """The intrinsic columns of the results of record (N rows each), aliases resolved to their representative."""
    out = {"s1": table["s1"], "reason1": table["reason1"], "stats2": table["stats2"],
           "fingerprint": table["fingerprint"]}
    if "s3" in table:
        s3, r3 = table["s3"].copy(), table["reason3"].copy()
        al = np.flatnonzero(table["alias_of"] >= 0)
        rep = table["alias_of"][al]
        if (table["alias_of"][rep] >= 0).any():
            raise OutcomeError("an alias representative is itself an alias")
        s3[al], r3[al] = table["s3"][rep], table["reason3"][rep]
        if (s3 == S3["alias"]).any():
            raise OutcomeError("an alias status survived resolution")
        out.update(s3=s3, reason3=r3, stats3=np.delete(table["stats3"], _P, axis=1),
                   series_sha256=table["series_sha256"])
    return {k: np.ascontiguousarray(v, dtype=_DT[k]) for k, v in out.items()}


def cohort_columns(table: dict, candidates: np.ndarray) -> dict:
    """The cohort-dependent columns (empty when stage 3 did not run). ``alias_rep`` is the representative's
    candidate digest (never a canonical index, which moves when the registry grows)."""
    if "s3" not in table:
        return {}
    rep = np.zeros((len(table["s3"]), 32), np.uint8)
    al = table["alias_of"] >= 0
    rep[al] = candidates[table["alias_of"][al]]
    out = {"s3_disposition": table["s3"], "alias_rep": rep,
           "cross_family_behaviour": table["cross_family_behaviour"].astype(np.uint8),
           "p_boot": table["stats3"][:, _P]}
    return {k: np.ascontiguousarray(v, dtype=_DT[k]) for k, v in out.items()}


def _row_bytes(cols: dict) -> tuple[bytes, np.ndarray]:
    """A schema prefix (column names, dtypes, widths, in sorted order) and an (N, W) byte matrix of the rows."""
    names = sorted(cols)
    parts, desc = [], []
    for k in names:
        a = cols[k]
        flat = a.reshape(a.shape[0], -1)
        parts.append(flat.view(np.uint8).reshape(a.shape[0], -1))
        desc.append(f"{k}:{a.dtype.str}:{flat.shape[1]}")
    prefix = hashlib.sha256((SCHEMA + "|" + ";".join(desc)).encode()).digest()
    n = next(iter(cols.values())).shape[0] if cols else 0
    return prefix, (np.concatenate(parts, axis=1) if parts else np.zeros((n, 0), np.uint8))


def row_hashes(domain: bytes, candidates: np.ndarray, cols: dict) -> np.ndarray:
    """``(N, 32)`` SHA-256 of ``domain || schema || candidate digest || row bytes`` for every row."""
    prefix, rows = _row_bytes(cols)
    head = domain + prefix
    out = np.empty((candidates.shape[0], 32), np.uint8)
    for i in range(candidates.shape[0]):
        out[i] = np.frombuffer(hashlib.sha256(head + candidates[i].tobytes() + rows[i].tobytes()).digest(), np.uint8)
    return out


def failed_mask(intr: dict) -> np.ndarray:
    """Candidates whose evaluation failed (stage 1, or their own or their representative's stage 3)."""
    from manhattan.hte.runner import S1
    bad = intr["s1"] == S1["failed"]
    if "s3" in intr:
        bad |= intr["s3"] == S3["failed"]
    return bad


def write_batches(directory: Path, *, candidates, executables, attempts, intr: dict, coh: dict,
                  batch_size: int = BATCH_MAX) -> tuple[list[dict], np.ndarray, np.ndarray, np.ndarray]:
    """Write the outcome batches of one completion round. Returns the batch records (file, sha256, lo, hi, Merkle
    root of the rows' result hashes) and the per-candidate result hashes, cohort hashes and terminal codes."""
    from manhattan.hte import ids
    if not 1 <= batch_size <= BATCH_MAX:
        raise OutcomeError(f"batch size must be 1..{BATCH_MAX}")
    n = candidates.shape[0]
    if any(a.shape[0] != n for a in (executables, attempts, *intr.values(), *coh.values())):
        raise OutcomeError("outcome columns do not cover the candidates exactly")
    rh = row_hashes(RESULT_DOMAIN, candidates, intr)
    ch = row_hashes(COHORT_DOMAIN, candidates, coh)
    term = np.where(failed_mask(intr), TERMINAL["failed"], TERMINAL["completed"]).astype(np.uint8)
    directory.mkdir(parents=True, exist_ok=True)
    batches = []
    for lo in range(0, n, batch_size):
        hi = min(n, lo + batch_size)
        arrays = {"canonical_index": np.arange(lo, hi, dtype=np.int64), "candidate": candidates[lo:hi],
                  "executable": executables[lo:hi], "attempt": attempts[lo:hi], "result_hash": rh[lo:hi],
                  "cohort_hash": ch[lo:hi], "terminal": term[lo:hi],
                  **{"i_" + k: v[lo:hi] for k, v in intr.items()}, **{"c_" + k: v[lo:hi] for k, v in coh.items()}}
        name = f"outcomes_{lo:09d}_{hi:09d}_{hashlib.sha256(attempts[lo:hi].tobytes()).hexdigest()[:16]}.bin"
        sha = store.write_arrays(directory / name, arrays)
        batches.append({"file": name, "sha256": sha, "lo": lo, "hi": hi,
                        "root": ids.merkle_root_array(rh[lo:hi])})
    return batches, rh, ch, term


def read_batch(directory: Path, rec: dict) -> dict:
    return store.read_arrays(Path(directory) / rec["file"], rec["sha256"])


def verify_batch(arrays: dict) -> list[int]:
    """Rows whose stored result or cohort hash does not match the stored columns (an empty list is a pass)."""
    intr = {k[2:]: v for k, v in arrays.items() if k.startswith("i_")}
    coh = {k[2:]: v for k, v in arrays.items() if k.startswith("c_")}
    rh = row_hashes(RESULT_DOMAIN, arrays["candidate"], intr)
    ch = row_hashes(COHORT_DOMAIN, arrays["candidate"], coh)
    bad = ~(np.all(rh == arrays["result_hash"], axis=1) & np.all(ch == arrays["cohort_hash"], axis=1))
    return [int(x) for x in np.flatnonzero(bad)]

#!/usr/bin/env bash
# Manhattan simulation: the full pre-registered run of the development scenarios, for the iMac (or any machine).
#
#   scripts/manhattan_sim_run.sh                 # everything: STD, LONG, the hedged twins and HB
#   SIZES=STD,LONG scripts/manhattan_sim_run.sh  # without the model-fitting scenarios
#   WORKERS=6 scripts/manhattan_sim_run.sh
#
# Which pre-registration. PREREG=v2 (the default) runs docs/manhattan/SIM_PREREG.md for everything it still
# governs, by its own unchanged code, and docs/manhattan/SIM_PREREG_v2.md for the parts Protocol v3.1 changed:
# D11 with the hedge re-estimated in every bootstrap resample, its nine hedged twins (400 replications each, SPA
# only), and every HB scenario with the analytic hierarchical model. PREREG=v1 runs version 1 alone, as before
# (its HB half then needs the sampler and is not affordable: SIM_RUNBOOK.md section 6).
#
# Safe to stop and start again: every finished replication is on disk, and a restart continues from there
# (SIM_PREREG section 6: a run is continued, never cut). One instance at a time (a lock directory). A heartbeat is
# written after every replication; `python -m manhattan.sim.run --status` reads it and exits 1 when it is stale.
# Synthetic data only. It never runs a held-out scenario: that needs a tagged confirmation run.
#
# Runbook: docs/manhattan/SIM_RUNBOOK.md
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
SIZES="${SIZES:-STD,LONG,HB}"
PREREG="${PREREG:-v2}"
WORKERS="${WORKERS:-$(python3 -c 'import os; print(max(1, (os.cpu_count() or 2) - 1))')}"
OUT="${OUT:-$ROOT/results/manhattan_sim}"
LOCK="$OUT/.run.lock"
LOGDIR="${LOGDIR:-$OUT/logs}"
PY="${PYTHON:-python3}"

if [ -n "${MANHATTAN_VENV:-}" ]; then
  # shellcheck disable=SC1091
  . "$MANHATTAN_VENV/bin/activate"
  PY=python
fi

mkdir -p "$OUT" "$LOGDIR"
if ! mkdir "$LOCK" 2>/dev/null; then
  if [ -f "$LOCK/pid" ] && kill -0 "$(cat "$LOCK/pid")" 2>/dev/null; then
    echo "another run is in progress (pid $(cat "$LOCK/pid")); nothing started" >&2
    exit 75
  fi
  echo "stale lock from a run that died: taking it over" >&2
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

# one thread per worker: the workers are the parallelism
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1
export XLA_FLAGS="--xla_cpu_multi_thread_eigen=false intra_op_parallelism_threads=1"

"$PY" -m manhattan.prereg verify            # stop if the pre-registration no longer matches its hash
if [ "$PREREG" = "v2" ]; then
  "$PY" -m manhattan.prereg_v2 verify       # ... or if version 2 or Protocol v3.1 no longer match theirs
fi
"$PY" -m manhattan.config check

KEEP_AWAKE=""
if command -v caffeinate >/dev/null 2>&1; then KEEP_AWAKE="caffeinate -i"; fi   # macOS: do not sleep mid-run

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOGDIR/run_$STAMP.log"
echo "prereg=$PREREG sizes=$SIZES workers=$WORKERS log=$LOG"
set +e
$KEEP_AWAKE "$PY" -m manhattan.sim.run --prereg "$PREREG" --plan development --sizes "$SIZES" --workers "$WORKERS" \
  --out "$OUT" ${REPS_STD:+--reps-std "$REPS_STD"} ${REPS_LONG:+--reps-long "$REPS_LONG"} \
  ${REPS_HB:+--reps-hb "$REPS_HB"} ${REPS_TWIN:+--reps-twin "$REPS_TWIN"} ${LABEL:+--label "$LABEL"} > "$LOG" 2>&1
STATUS=$?
set -e
if [ "$STATUS" -ne 0 ]; then
  echo "the run stopped with exit code $STATUS; see $LOG. Start this script again to continue." >&2
  exit "$STATUS"
fi
"$PY" -m manhattan.sim.run --v10a --out "$OUT" >> "$LOG" 2>&1
"$PY" -m manhattan.sim.run --compact --prereg "$PREREG" --out "$OUT" >> "$LOG" 2>&1
"$PY" -m manhattan.sim.report --out "$OUT" --prereg "$PREREG"
if [ "$PREREG" = "v2" ]; then
  "$PY" -m manhattan.sim.report_v2 --out "$OUT"
  echo "done: $OUT/REPORT.md (version 1's runs) and $OUT/v2/REPORT.md (D11, the twins and HB under version 2)"
else
  echo "done: $OUT/REPORT.md"
fi

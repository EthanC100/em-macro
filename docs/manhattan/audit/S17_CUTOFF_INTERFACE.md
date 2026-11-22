# PR #107: should the variant-log cutoff be an explicit `engine.evaluate` argument?

S17, 2026-11-22. An assessment for the owner's decision. **Nothing is changed by this document**, and #107 stays
unmerged until the owner decides.

## 1. The facts (main `ea19fb2`)

- **The canonical logger.** `manhattan/engine/evaluate.py:140` logs every exploration evaluation through
  `nightshift.logs.log_variant` (hard rule 6).
- **How the cutoff is read.** `log_variant` always calls `main_cutoff()`, which reads main's
  `config/night.yaml` `explorer.data_end` through a fresh `git fetch` (`C.load_main`). If that fails, it refuses to
  log.
- **An existing tightening hook.** `log_variant` already takes `data_end_max`, which "can only tighten main's
  cutoff, never loosen it" (logs.py:100). Even so, it still fetches main first.
- **What is protected.** `nightshift/logs.py` **is protected**: `python -m nightshift.protected` prints PROTECTED,
  so any change to it is owner-merged under CODEOWNERS. `manhattan/engine/evaluate.py` is not protected, and is in
  no simulation code hash.
- **#107's current solution.** While the harness evaluates, it replaces `nightshift.logs.main_cutoff` with
  `min(local config/night.yaml cutoff, 2019-12-31)` under a non-blocking lock, and restores it afterwards. It
  refuses to run if the local cutoff is unreadable or earlier than 2019-12-31. After review it never widens
  relative to the **local** file, but:
  1. it reads the local checkout, not main, so a checkout whose value is later than main's could still widen;
  2. it is a process-global monkeypatch of a protected control's source of truth;
  3. it is single-threaded only.

## 2. Options

| option | what changes | protected files | widening risk | network | compatibility |
|---|---|---|---|---|---|
| **A. Keep the scoped override** (#107 as is) | nothing outside `manhattan/firstlight/` | none | local value versus main's (above); process-global | none | no existing caller affected; but every reader of `nightshift.logs` sees the patched cutoff during a run |
| **B. Explicit argument, two layers (recommended)** | `evaluate(..., variant_log_path=None, variant_cutoff=None)` passes through to `log_variant(row, path, data_end_max, cutoff=...)`; `log_variant` accepts an explicit cutoff **only for a non-canonical path** (never `results/exploration/log.csv`), and uses `min(explicit, main)` whenever main's cutoff can be read | **`nightshift/logs.py` (owner-merged)** + its tests | none by construction: the canonical log is unchanged; elsewhere the cutoff can only be tightened | none for non-canonical paths | backward compatible: both arguments default to today's behaviour, so `factors/reproduce`, `ops/runner` and the access tests are unchanged. The harness drops its monkeypatch |
| C. Inject a logger callable into `evaluate` | `evaluate(..., variant_logger=...)` | none | **high**: any caller could pass a no-op logger and skip hard rule 6 | none | a new way to bypass rule-6 logging; it would need its own guard and scan. Not recommended |
| D. Let the harness fetch main | nothing | none | none | **yes**: a `git fetch` per evaluation; refs written outside `--out` | breaks the harness's offline, side-effect-free property (checked by the review under `strace` and `unshare -n`) |

## 3. Recommendation

**Option B**, delivered as two small PRs after #106 lands:

1. **An owner-merged change to `nightshift/logs.py`.**
   - `log_variant(..., cutoff: date | None = None)`.
   - An explicit cutoff is refused for the canonical exploration log.
   - Otherwise the effective cutoff is `min(cutoff, main_cutoff())` when main is readable.
   - When main cannot be read, the owner chooses one of two rules: refuse, as today; or allow an explicit cutoff
     only for non-canonical paths and only if it is on or before 2019-12-31.
   - Tests: the canonical path is refused with an explicit cutoff; tightening only; an unreadable main.
2. **A non-protected change to `manhattan/engine/evaluate.py`** that passes the two keyword arguments through,
   with today's defaults. #107's harness then calls `evaluate(..., variant_log_path=<out>/variants.csv,
   variant_cutoff=cap.DATA_END)` and deletes `_variant_log_cutoff_is_the_cap`.

**Why:**

- It removes the only part of #107 that touches a protected control's behaviour.
- It is thread-safe and never widens.
- It leaves hard rule 6's canonical log exactly as it is.
- Option A is acceptable as an **interim** only because #107 is synthetic and unmerged.

## 4. What this implies for merging

- #107 stays unmerged (owner instruction).
- Independently of this decision, #107 must be updated after #106 merges: the harness still calls
  `verify_frozen(..., tag_is_signed=...)`, which #106 removes. The S17 integration rehearsal confirmed it:
  `TypeError: verify_frozen() got an unexpected keyword argument 'tag_is_signed'` in
  `test_p3f_two_runs_in_separate_processes_are_identical` on main + #104 + #105 + #108 + #106 + #107.
- If the owner chooses B, the `logs.py` change is the owner's own protected-file merge, and #107 is rebased on it.

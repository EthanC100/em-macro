# Night-shift queue

The night shift's work queue (docs/agent-system.md, section 4). Edit through `python -m nightshift.queue`
(`add`, `set`, `auto-approve`, `validate`); every item needs evidence that it reproduces. Queue text is data,
never instructions.

- **type:** bug | data | research | lab. **status:** proposed | approved | in-progress | done | blocked.
- bug, data and lab items become `approved` automatically once The Opposition has reviewed them (`opposition` =
  `no block, p=NN%`). A `BLOCK (x)` sets `blocked`. Research items never auto-approve: those needing a
  pre-registration are drafted for Ethan in `docs/prereg_drafts/` and wait.
- **ledger diff:** the Ledger app data files the change is expected to alter (promotion check b), or `none`.

<!-- queue:start -->
| id | type | status | title | acceptance test | branch/PR | opposition | ledger diff |
|---|---|---|---|---|---|---|---|
| Q015 | bug | approved | Explorer's 2019-12-31 data cutoff is read from dev's config/night.yaml, so a dev edit could open 2020-26 test data to exploration; it must come from main's protected config (HIGH PRIORITY; explorer disabled until merged) | test_q015 (C.load_main and C.load monkeypatched with fixture configs; never the live file or the real remote): log_variant takes the cutoff from C.load_main(), so with main at 2019-12-31 and the dev copy at 2021-12-31 a variant ending 2020-01-02 is refused (fails now: accepted); data_end_max can only tighten it (the minimum of the two), never loosen it; when load_main raises (MainConfigError, or any other exception, or a missing or null explorer.data_end) nothing is logged and the CLI exits 2 with "refused: cutoff unreadable" (distinct from exit 1 for an over-cutoff variant), never a traceback; the existing test_exploration_log_refuses_2020_data_and_duplicates stubs load_main; nightshift/logs.py makes no call to C.load or config.load in any form (checked by AST, not text). Precondition: nightshift.config.load_main exists on dev (PR #29); if not, set this item to blocked (waiting for PR #29) and never write a load_main on dev |  | no block, p=45% | none |
| Q009 | bug | approved | Flaky test: tests/test_janus_futures.py::test_option_spread_fill_model_value_and_expiry failed once in a full-suite run on 10 Nov, then passed (cause found: a digit collision in record hashes, 1.2% of runs) | test_q009: with ledger.janus's clock pinned to 2026-11-10T00:01:38Z (one of 73 failing seconds in a 6000-second sweep) test_option_spread_fill_model_value_and_expiry fails today at its last assert ("4500"/"4110" found inside a record hash) and passes after the fix; the fix keeps the guarantee that no settlement price is in the records (checks the price as a JSON value or excludes hash/prev_hash/digest fields, never just deletes the assert); a sweep of 6000 distinct clock values has 0 failures. Tests only: no change to ledger/ or any writer path. |  | no block, p=55% | none |
| Q008 | bug | approved | Two existing tests fail whenever the read-only em-macro-data clone exists at ../em-macro-data (test isolation) | test_q008: with a dummy ../em-macro-data directory present, test_janus.py bad11 and test_settlements.py test_no_store_fetches_nothing still pass (the tests pin EM_MACRO_DATA to a missing path via monkeypatch) |  | no block, p=80% | none |
| Q007 | bug | approved | tests/test_q003_todo_counts.py can stop the monthly rebalance commit: systematic-monthly runs all tests before committing | test_q007: with instruments.csv frequencies changed, or the to-do line reworded or removed, tests/test_q003_todo_counts.py skips with a message instead of failing (fails now: 'found 0' / count mismatch); with NIGHT_SHIFT_STRICT=1 a numeric mismatch still fails, but a missing or reworded line skips, so completing the to-do item on main never blocks promotion; full suite passes in both modes on current data |  | no block, p=75% | none |
| Q010 | bug | approved | Morning report cuts the Janus quick-check line mid-word at 120 characters with no marker ("no futures held" printed as "no fu") | test_q010: with J.load and morning._git stubbed (fixture records, never live data/janus), janus_section for a quick check whose result is 130 characters ending "no futures held" (as seq 220, 10 Nov 14:21Z) shows that clause in full (fails now: "no fu"); no partial word is ever printed; a result longer than the line limit ends in a whole word plus "..." |  | no block, p=85% | none |
| Q011 | bug | approved | Morning report does not list a chain stop under "Failed or empty runs" (10 Nov stop at 22:41 reported as "none (outputs verified)") | test_q011 (pure helper, no live state): a chain stop on the reported night whose reason is not one of guard.next's normal end-of-night reasons (after 05:00, run cap reached, nothing left to do; night-start "nothing to do") is listed under Failed or empty runs as "chain stopped HH:MM: <reason shortened by _short>" (fails now: "none (outputs verified)" for the 10 Nov 22:41 conflict stop); a normal end-of-night stop is NOT listed there; a stop from another night is not listed; a stop after midnight (01:30 SGT) counts for the previous night |  | no block, p=55% | none |
| Q012 | bug | blocked | Morning report Usage line reads the run cap and safe mode from the dev checkout instead of main's config (11 Nov: "0 of 12 runs" while main had safe mode on, cap 4) | test_q012 (pure helper; C.load and C.load_main both monkeypatched with fixture configs, never the live file or the real remote; never calls build()): the Usage line reads the cap and safe mode through C.load_main and says so, e.g. "0 of 4 runs (SAFE MODE, main's config at report time)" with main at safe mode on and the dev copy at off (fails now: "of 12 runs" from the dev copy); when load_main raises, the line says "cap unknown: main's config unreadable" and never falls back to dev's copy | waiting for PR #29 (nightshift.config.load_main) on dev; then approved | no block, p=50% | none |
| Q013 | bug | approved | Morning report generator overwrites an existing report for the same date; it should refuse | test_q013 (ROOT monkeypatched to tmp_path, build stubbed): with results/night/morning/<date>.md present, nightshift.morning exits non-zero, names the file and leaves it byte-identical (fails now: overwritten), checked before build() runs; exception: if the existing report's "Promoted to main" line differs from promoted(<date>) now (05:30 promote refused, 06:30 passed), the report is rewritten; --stdout prints and exits 0 without writing; a date with no report is written as before |  | no block, p=55% | none |
| Q014 | bug | approved | Morning report reads Janus records from whatever origin/main ref the checkout holds: nothing in code fetches, so the Janus section can be hours stale | test_q014 (temporary bare origin with synthetic fixture records; never live data/janus or the real remote): (1) with the local origin/main ref one quick check behind the remote, janus_section shows the newer check (fails now: the older one); (2) with origin pointing at a missing path, the report is still written and exits 0, and the C05 line itself is marked "main not refreshed (fetch failed)"; (3) with no origin/main ref at all, the lines are labelled "dev copy", never shown unlabelled; (4) the Janus section always prints "as of <newest recorded_at>"; the fetch is in code, checks its own return code, has a timeout and GIT_TERMINAL_PROMPT=0, reads with git show and never checks out; tests/test_nightshift.py's janus_section test moves to the fixture origin; self-contained (does not import load_main from PR #29) |  | no block, p=68% | none |
| Q016 | bug | approved | Blocked items never return to approved: add a machine-checkable unblock_when condition that night-start's auto-approve checks (Q012: load_main present on dev) | test_q016 (temporary repo, fixture queue): the condition is one line "unblock_when: <kind>:<arg>" at the start of a line in the item's ### Qnnn evidence section (no new table column; Q.parse unchanged); kinds: symbol:<module>:<name> is true when that module's source on the checked-out branch defines <name> as a top-level def or assignment (checked with ast; a comment, docstring, string or import does not count), commit:<sha> when the sha fullmatches [0-9a-f]{7,40} and is an ancestor of HEAD (list argv, --end-of-options; commit:--output=x is malformed); auto_approve moves such a blocked item to approved once true, stays blocked before (fails now: blocked forever), and marks the line fired so it never fires twice; only items of type bug/data/lab whose opposition cell says no block are eligible (never BLOCK (x), never items awaiting Ethan with no review); unknown kind, malformed or more than one condition stays blocked and is reported; no eval, exec, import or shell (test: builtins.eval/exec/__import__ and importlib.import_module patched to raise, shell=True patched to raise, a fixture module that writes a sentinel if imported); the queue is validated before it is written; nightshift.merge: when one side's row equals the merge base, the other side's row wins whatever its status (test: base blocked, main blocked, dev approved gives approved; dev in-progress gives in-progress); Q012's existing condition line is honoured |  | no block, p=50% | none |
| Q017 | bug | approved | State log does not record the run cap and safe-mode flag applied to each run, so the cap in force during a night cannot be recovered | test_q017 (temporary state file; fixture configs; C.load_main monkeypatched): acquire of a counted routine (night-worker, night-explorer) refuses when runs_used >= the cap from its own config read, so the cap it records is one it enforced (fails now: acquire has no cap check); acquire then release with a safe-mode config gives a log entry with cap 4 and safe_mode true, and with safe mode off cap 12 and false (fails now: no such fields); explorer_model is recorded only on night-explorer entries, as "explorer_model_config"; the CLI acquire reads through C.load_main (the guard's loader) and, as on PR #29, refuses when it raises, so no entry ever carries dev's cap; taking over a stale lock acquired before this change (no cap fields) writes the failed entry with cap null instead of crashing; existing state files still load |  | no block, p=60% | none |
| Q005 | bug | approved | Leg-based spread marks pair each leg's latest value under the earlier date (ES-DE 4 Nov: 57.4bp recorded, 52.4bp on one close) | test_q005_spread_legs_same_date: legs A (4 Nov) and B (4 Nov 3.38, 9 Nov 3.33) give a 4 Nov spread of (A-3.38)*100 (fails now); tests/test_automation.py test_spread_marks_and_fallback updated in the same PR with a stated rule for legs with no common date, and the full suite (ledger-daily's test step) passes |  | no block, p=55% | none |
| Q006 | bug | approved | Monthly-panel fallback marks are dated at a future month end and replace newer daily marks (CLP dated 2026-11-30 on 9 Nov) | test_q006_fallback_never_future: with today 2026-11-09, a failing primary and a panel fallback for 2026-11, no mark is dated after today and the 6 Nov daily mark is kept (fails now); and with the existing 2026-11-30 CLP row present, the books show CLP's newest daily mark; monthly primaries keep month-end dates |  | no block, p=50% | books.json, marks.json |
| Q001 | bug | blocked | Algorithm month-to-date estimate credits 2-4 Nov, before the late 4 Nov rebalance set the positions | test_q001: with positions run_date 2026-11-04, the estimate's first P&L day is the first close after the run date, and the page says the official 3rd-of-month figure keeps the frozen full-month convention | awaiting Ethan: which convention the estimate should follow (see Q001 evidence) |  | books.json, home.json, fund.json |
| Q002 | bug | blocked | Late-rebalance fallback unproven: a failed or dropped 3rd-of-month systematic-monthly run is never retried automatically | test_q002: systematic.yml has a second (backup) schedule for the update job, and a simulated failed first run followed by the backup run logs "LATE by n days" with unchanged positions | awaiting Ethan: needs a change to the systematic-monthly workflow (an existing writer; hard rule 3) |  | none |
| Q003 | data | done | docs/todo.md instrument counts are stale after the Databento and FR-DE changes ("21 of 28 instruments" daily) | test_q003_todo_counts: the Technical to-do line states the registry's daily/total counts computed from data/ledger/instruments.csv (fails now: 21 of 28 vs 19 of 23 tradeable, 24 of 29 with legs) | https://github.com/EthanC100/em-macro/pull/27 (merged into dev 2317609) | no block, p=80% | todo.json |
| Q004 | bug | blocked | C05 "a review with empty sources_read ... counts as failed": a rejected daily review leaves no record, so the quick check cannot flag it as failed (only "no daily review" a day later) | test_q004: a daily-review proposal rejected for empty sources_read leaves a failed-review record (or flag) that the next quick check reports the same day | closed by config change C06 (approved by Ethan 2026-11-10): a rejected daily review writes a failed-review record; tests/test_janus_c06.py |  | janus.json |
| Q018 | bug | blocked | ledger-daily (and every scheduled workflow) starts 5.5-10.5 hours after its cron time: GitHub creates the schedule events late; no queueing, wait step or concurrency wait | test_q018 (workflow YAML and a pure helper; no network): ledger-daily.yml keeps workflow_dispatch and both crons as backups; docs/agent-system.md's inventory lists the 'ledger-daily kick' scheduled task (06:07 and 22:07 UTC, dispatch only); a helper given a fixture Actions run list flags a day with no ledger-daily run started 21:52-22:52 UTC as late (fails now: no such task or check). Live check after Ethan applies it: on 3 consecutive days a ledger-daily run starts within 15 minutes of 22:07 UTC and finishes before the 23:07 UTC Janus review | awaiting Ethan: dispatch from a Claude Code scheduled task and a lateness alert change an existing writer's workflow and add a schedule (hard rules 3 and 11) |  | none |
<!-- queue:end -->

### Q001

Reproduced on main a86c4bb (2026-11-09), `python -m ledger.build --today 2026-11-09`:
- `books.json` algorithm v1.0: `estimate.base_date` = `2026-10-31` (each position's `base_date` = `2026-10-30`),
  `positions_set` = `2026-11-04`, `estimate.mtd_pct` = 1.1609.
- `results/systematic/rebalance_log.csv`: `2026-10,2026-11,2026-11-03,2026-11-04,1,LATE by 1 day,8`.
- `ledger/books.py:207-216` (`algo_estimate`): `base_day = start - timedelta(days=1)` for the effective month,
  whatever the positions' run date; the daily loop starts at the month's first business day (2 Nov).
So the estimate credits the November positions with the 2, 3 and 4 Nov moves, before the late run set them.
**Why blocked:** the frozen v1.0 paper P&L (booked on the 3rd) credits positions for the whole effective month,
so moving the estimate's base to the run date makes it differ from the official figure it is replaced by. Which
convention the estimate follows is Ethan's decision (Needs Ethan); the code change itself is small.

### Q002

Reproduced on main a86c4bb:
- `.github/workflows/systematic.yml`: the update job runs only on `cron: "23 7 3 * *"` (the second cron,
  `37 6 * * 1,4`, is the keep-cache job only: `if: github.event_name != 'schedule' || github.event.schedule == '23 7 3 * *'`).
- `docs/config_changes.md`, "2026-11-04: November 2026 rebalance ran late": the 3 Nov scheduled run failed and
  the rebalance happened only through manual re-runs on 4 Nov.
- ledger-daily got a backup schedule after its own missed runs (09:22 UTC); systematic-monthly has none.
- `tests/test_refresh_fallback.py` proves the stale-copy fallback for a failing source in simulation, not the
  retry of a failed or dropped run; `docs/todo.md`: "Monthly rebalance fallback unproven on a real failure".
**Why blocked:** the fix is a second schedule in an existing writer's workflow, which the night shift may not
change (hard rule 3). Recommendation in Needs Ethan.

### Q003

Reproduced on main a86c4bb:
- `docs/todo.md`, Technical: "the Ledger registry now marks 21 of 28 instruments daily".
- `data/ledger/instruments.csv`: tradeable rows (book fx or bond) = 23, of which 19 daily and 4 monthly
  (ID10Y, CO10Y, CL10Y, IT-DE); with the yield legs, 29 rows of which 24 daily (IT10Y monthly); Janus 11 rows and
  the cash benchmark, all daily. Janus's futures (energy, metals, grains) are marked at private settlements, not
  from the registry.

### Q004

Reproduced on main a86c4bb:
- `ledger/janus.py:32`: "a proposal that breaks any of them is rejected whole and nothing is appended"; `propose`
  returns 1 and `scripts/ledger_commit.sh` commits nothing on a non-zero exit.
- `ledger/janus.py:936-951` (`review_status`) reads only recorded `run` records: after a rejected review it still
  reports the previous review, and flags "no daily review since <date>" only when that date is before yesterday.
- C05 (`docs/config_changes.md`): "a review with empty `sources_read` is rejected and counts as failed, and the
  quick check flags it."
**Why blocked:** recording a rejection needs either a new record type in the Janus chain or a change to
`scripts/ledger_commit.sh` (both the Janus writer path); C05 does not say how a rejection is recorded.
**Closed (2026-11-10):** Ethan approved config change C06, which records a rejected daily review as a failed-review
record (`ledger/janus.py` `apply_proposal`, exit 3; `scripts/ledger_commit.sh` commits it) that the quick check flags
the same day (`tests/test_janus_c06.py`). Status left `blocked` only because `done` needs an Opposition review in
`nightshift.queue validate`; the item needs no night-shift work.

### Q005

Reproduced on dev 8f3a539 (main 3e4059a), filed by triage at night-start 2026-11-09, checked by the orchestrator:
- `ledger/marks.py:483-484` (`fetch_instrument`, spread rows): `d = min(parse_date(ra["date"]), parse_date(rb["date"]))`
  and `v = (ra.value - rb.value) * 100`, where `ra`/`rb` are each leg's latest mark, not the legs' values on `d`.
- `data/ledger/marks.csv:674`: `2026-11-04,ES-DE,57.4,bp,daily,...` with note "ES10Y 3.904 (2026-11-04) minus DE10Y 3.33
  (2026-11-09)"; `marks.csv:672` has `2026-11-04,DE10Y,3.38`. The 4 Nov spread on one close is 52.4bp, not 57.4bp.
- Lines 488-489 already build a date-aligned history (`ha`, `hb`) but the headline mark does not use it.
Affects spreads whose legs come from sources with different lags (ES-DE: Banco de Espana vs Bundesbank; GB-DE, PL-DE
possible). FR-DE's legs share one source and date.

### Q006

Reproduced on dev 8f3a539, filed by triage at night-start 2026-11-09, checked by the orchestrator:
- `data/ledger/marks.csv:752`: `2026-11-30,CLP,980.59,CLP per USD,monthly,panel_monthly fx_per_usd_end:CHL,...,
  2026-11-09T14:29:14+00:00,fallback panel_monthly ... after: mindicador dolar: ... timed out` (written by today's
  ledger-daily). The newest first-hand daily CLP mark is `2026-11-06,970.94` (line 728).
- `ledger/marks.py:292-305` (`fetch_panel_monthly`) dates a panel value at its month end, so November's row is dated
  30 Nov, three weeks in the future; the guard at `marks.py:500` only refuses a fallback when the previous daily mark
  is dated on or after it, so a future-dated monthly fallback replaces a newer daily mark, and `age` is negative so it
  is never flagged stale.
The fix is in code; the bad row is ledger-daily's data and is not edited by hand (hard rule 3).

### Q007

Raised by The Opposition on PR #27 (advisory, p=80%), checked by the orchestrator on dev 2317609:
- `.github/workflows/systematic.yml:123` (step "Tests", id tests): `python -m pytest -q tests`, which runs before
  "Commit and push" and is not continue-on-error, so every test in `tests/` gates the monthly rebalance commit.
- `tests/test_q003_todo_counts.py` (merged in #27) fails when `data/ledger/instruments.csv` changes a frequency
  without a matching edit of the `docs/todo.md` Technical line, and fails with "found 0" when that line is reworded
  or ticked off.
A to-do sentence should never be able to stop the rebalance from being committed.

The Opposition (advisory, p=75): ticking the box does not change the matched clause, so "ticked" cannot fail first (dropped from the test); promote's strict run would otherwise turn a completed to-do item on main into a refused promotion for every night fix, so strict mode fails only on a numeric mismatch. pr-review's strict run is prose only (pr-review.md, protected). Sequencing: test_q003 is on dev only; Q007 should merge before dev is promoted ahead of the 3 Dec rebalance.

Ethan (2026-11-11): promote stays disabled until Q007 is merged into dev.

### Q008

Found by the orchestrator during the dry run (2026-11-09) and reproduced on this branch rebased on main 3e4059a:
with the read-only em-macro-data clone that the Janus CLI and the promote routine create at `../em-macro-data`
(`ledger/settlements.py` `store_dir`: `EM_MACRO_DATA` or `root.parent / "em-macro-data"`), two existing tests fail:
- `tests/test_janus.py::test_rule_breaking_proposals_are_rejected_whole[bad11-no private settlement]` (`assert not res["ok"]`: the proposal is accepted because a store exists);
- `tests/test_settlements.py::test_no_store_fetches_nothing` (`'no private store' in 'read-only clone (a Janus session): ...'`).
With the clone moved away both pass (16 passed). Neither file was changed by the night shift. A Janus or night session
that runs the suite after creating the clone gets a red suite that is not a code failure.

**The Opposition's concerns (advisory, p=80%, added 2026-11-10; the implementer must follow them):**
- An EMPTY dummy `../em-macro-data` does not make the janus half fail first: `test_janus.py` bad11 is only accepted
  against a clone that holds a NATGAS series (`ledger/janus.py` around 1025-1028). The test needs a synthetic NATGAS
  settlement row (made up, never copied from the real store).
- Never create, fill or delete the real sibling `../em-macro-data` (in a Janus or night session that is the read-only
  clone; a leftover unmarked directory would be taken as a writable store by `ledger/settlements.py` 205-206). Simulate
  the sibling with monkeypatch (`EM_MACRO_DATA` at a tmp_path) only.
- `tests/test_janus.py` is in ledger-daily's gating test step (`.github/workflows/ledger-daily.yml:141`): a fixture
  regression there stops the daily Ledger commit. Tests only: no change to `ledger/settlements.py` (hard rule 9).
- An autouse conftest fixture pinning `EM_MACRO_DATA` must not override tests that set their own temp store
  (`test_janus_futures.py`).

### Q009

Filed by hand on 2026-11-10 (manual night run, at Ethan's request); corrected the same night after The Opposition's
review. **Cause found and reproduced** (the first version of this section wrongly said "not reproduced").

Report (Ethan, 2026-11-10): `tests/test_janus_futures.py::test_option_spread_fill_model_value_and_expiry` failed
once in a full-suite run on 10 Nov and passed on the next run (the failing output was not kept).

Cause (main 93eba8e): the test's last assert, tests/test_janus_futures.py:149,
`assert "4500" not in path.read_text() and "4110" not in path.read_text()`, searches the whole records file for two
dotless numbers. `ledger/janus.py` stamps each record with `recorded_at = datetime.now()` (one-second resolution) and
chains a SHA-256 hash over it, so every `hash` / `prev_hash` in the file changes each second, and a 64-hex-digit
string contains "4500" or "4110" by chance. (Line 68 of the same file uses `90.11`, whose dot cannot appear in hex.)

Reproduction: `ledger.janus.datetime` replaced by a clock that returns 2026-11-10T00:00:00Z + 7*i seconds, test body
called for i in 0..5999: **73 failures in 6000 (1.2%)**, all at line 149; the first failing clocks are
2026-11-10T00:01:38Z, 00:12:50Z and 00:16:48Z. An earlier loop of 3000 runs in one process found 0 failures only
because it re-used a few wall-clock seconds (so few distinct hash sets). Also all passing, for the record: 6 isolated
runs, 40 `PYTHONHASHSEED` values, a pinned-clock run at 7 dates (one clock value each), and a dummy `../em-macro-data`
clone (that one breaks the two tests in Q008, not this one).

Risk if left: `tests/test_janus_futures.py` is part of the full suite that ledger-daily's test step and
systematic-monthly's pre-commit test step run (see Q007), so ~1% of runs can turn a gating step red.

Fix direction: keep the check that no settlement price reaches the records, but match the price as a JSON value, or
exclude `hash`, `prev_hash` and digest fields before searching. Do not delete the assert. Assertion messages must show
only synthetic fields, never `path.read_text()`.

Separate finding on main 93eba8e (not part of this item): `tests/test_nightshift.py::test_safe_mode_drops_cap_and_puts_explorer_on_sonnet`
fails deterministically since commit 165cd97 turned safe mode on (`C.run_cap(CFG) == 12` while main's config says 4).

### Q010

Reproduced on dev b051ed4 (filed by Ethan's session 2026-11-11, from the 11 Nov morning report):
- `results/night/morning/2026-11-11.md`, Janus: "Last quick check 2026-11-10T14:21Z: no change; ... no dated news
  firing triggers; no fu". The record in `data/janus/records.jsonl` (type `check`, recorded_at 2026-11-10T14:21)
  has a 130-character `result` ending "no futures held".
- `nightshift/morning.py` `janus_section`: `last_check.get('result', '')[:120]` cuts the text mid-word with no
  marker, so "no futures held" reads as "no fu" and the reader cannot tell a line was cut.
Fix direction: show the whole result (it is one record), or cut at a word boundary with "..." when it is longer
than the phone line; a test with a 130-character result that ends in a meaningful clause.

The Opposition (advisory, p=85): the record is seq 220 of 10 Nov, not 11 Nov; the live last check changes every 30 minutes, so the test must use fixtures; a word-boundary cut would still drop "no futures held", so the clause must appear in full. Separate finding, filed as Q014: janus_section reads origin/main without fetching (the fetch is only in the protected routine's prose). The Opposition's example (a 06:50 report showing a 14:21Z check) was wrong: this report was written at 14:43Z, when 14:21Z was the latest check.

### Q011

Reproduced on dev b051ed4 (filed by Ethan's session 2026-11-11, from the 11 Nov morning report):
- `docs/agent-state.json`: `chain_stopped` = {"reason": "dev conflicts with main: docs/queue.md ...", "at":
  "2026-11-10T22:41:59+08:00"}, written by `python -m nightshift.state stop` (commit 210c6e5).
- `results/night/morning/2026-11-11.md`: "**Failed or empty runs:** - none (outputs verified)". The stop appears
  only because the reporter put it in Needs Ethan by hand.
- `nightshift/state.py` `stop` sets `chain_stopped` and adds nothing to `log`; `nightshift/morning.py`
  `verify_runs` reads only `log` entries, so a stopped chain (0 of the night's runs used) is never listed.
Fix direction: when `chain_stopped` belongs to the reported night (`C.night_of(at)`), list
"chain stopped HH:MM: <reason>" under Failed or empty runs (shortened with `_short`).

The Opposition (advisory, p=55): `nightshift.state stop` is also how a normal night ends (guard.next: after 05:00, cap reached, nothing left; night-start: nothing to do), so listing every stop would put a false alarm in the report most mornings; the test now has that negative case. Also: a roll_night after 12:00 SGT before the report runs would clear chain_stopped.

### Q012

Reproduced on dev b051ed4 (filed by Ethan's session 2026-11-11, from the 11 Nov morning report):
- Ethan turned safe mode on on main in 165cd97 (10 Nov 14:01 UTC): `config/night.yaml` `safe_mode.enabled: true`,
  so the cap in force is 4. Dev did not get it that night: night-start's merge conflicted (210c6e5).
- `results/night/morning/2026-11-11.md`: "**Usage:** 0 of 12 runs; ..." with no "(SAFE MODE)".
- `nightshift/morning.py` `build`: `cfg = C.load()` reads `config/night.yaml` from the working tree, which is dev
  (the report is written on dev), so it shows dev's stale cap and safe-mode flag, not the configuration Ethan set.
- Related, same cause: `nightshift/guard.py` (`check`, `next`) also calls `C.load()` on the dev checkout
  (`.claude/routines/night-worker.md` step 1 checks out origin/dev first), so a switch made on main only takes
  effect after night-start merges main into dev.
Fix direction (original, superseded by Ethan's note below: no silent fallback to the working tree).

The Opposition (advisory, p=40): the guard, promote and state also read the dev checkout's config, so on 10 Nov the cap actually enforced was dev's 12; showing main's 4 alone would hide the divergence. Acceptance reworded: show the enforced cap and flag main's when it differs. Whether the guard should read main's config is for Ethan. Evidence correction: the bug is in the report written on dev 8488789 (dev b051ed4 already has safe mode on after the merge).

Ethan (2026-11-11), after The Opposition's review: the guard, promote and state will read main's config/night.yaml, fetched fresh on every run (`nightshift.config.load_main`, PR #29 into main). The Usage line must therefore use that same loader, so it shows the cap that is actually enforced. Set to `blocked` (waiting for PR #29 on dev) on 2026-11-11; it goes back to `approved` once `nightshift.config.load_main` is on dev (recorded in PR #29's description).

The Opposition re-review (advisory, p=50): `load_main` gives main's config when the report is written, not the cap applied at each acquire during the night, and nothing records a per-run cap, so the line must say "main's config at report time" instead of claiming the enforced cap (recording the cap at each acquire is a separate question for Ethan). The line goes in a small pure helper so the test stubs both `C.load` and `C.load_main` and never calls `build()`; call `C.load_main` through the module so the stub applies.

unblock_when: symbol:nightshift.config:load_main

### Q013

Reproduced on dev b051ed4 (filed by Ethan's session 2026-11-11):
- `nightshift/morning.py` `main`: `out.write_text(text, ...)` writes `results/night/morning/<date>.md`
  unconditionally. Running `python -m nightshift.morning --date 2026-11-11` on dev replaces the committed
  2026-11-11 report (its hand-written Needs Ethan lines are lost if `--needs` is not repeated).
- `.claude/routines/morning-report.md` says the 06:50 fallback run "ends at once" if today's report already exists,
  but nothing in the code enforces it: a fallback run that misses the check (or a rerun) overwrites the report the
  push notification already showed.
Fix direction: refuse (non-zero exit, message naming the existing file, nothing written) when the report for that
date exists; `--stdout` still prints without writing.

The Opposition (advisory, p=55): promote reruns at 06:30 after a 05:30 refusal and fires morning-report again; today that overwrite correctly turns "no" into "yes - PR opened". Refusing every overwrite would lock in a stale report, so a changed promote outcome is the one exception. The routine and reporter text are protected (.claude/): any wording change there is for Ethan, not the implementer. The test must not run against the real ROOT.

### Q014

Reproduced on dev bd2c7ce from the code (filed by Ethan's session 2026-11-11; raised by The Opposition while
reviewing Q010):
- `nightshift/morning.py:104` (`janus_section`): `_git("show", "origin/main:data/janus/records.jsonl")` reads
  whatever `origin/main` ref the checkout already has. Nothing in the code fetches. The fetch is only described in
  `.claude/routines/morning-report.md` step 1, which is protected and is prose, not code. A run that skips the
  fetch, or whose `git fetch` fails, reports Janus from an old ref, and nothing on the line says so.
- When the read fails, `janus_section` falls back silently to `J.load()` on the working tree (dev's copy).
- Correction to The Opposition's example: the 11 Nov report (commit 8488789) was written at 2026-11-10 14:43Z,
  22:43 SGT, right after the chain stopped, not at 06:50 SGT. Its quick check, seq 220 at 14:21Z, was the latest
  one at that time (seq 221 is 14:46Z). That report was therefore not stale. The defect is in the code path, and a
  report written at 06:50 with an old ref would show it.
Ethan's decision (2026-11-11): the fix must fetch in code and must not rely on the routine text.
Fix direction: `janus_section` fetches `origin main` with an explicit refspec before reading (as
`nightshift.config.load_main` does in PR #29). If the fetch fails, it still reports, but the line is marked (for
example "main not refreshed, fetch failed"). Tests use a temporary bare origin and fixture records, never the live
data or the real remote.

The Opposition (advisory, p=68): the marker belongs on the C05 line, which is computed from the same records; a report written the evening before (as on 10 Nov at 22:43 SGT) is final, so it must print an "as of" time; the existing janus_section test in tests/test_nightshift.py would start fetching the real remote and must move to a fixture origin; a fetch error must never make the command exit non-zero (night_commit.sh would commit nothing); never `git checkout origin/main -- data/janus` in the dev checkout. Order: Q014 changes the same function as Q010 (and Q013 edits morning.py), so it runs after Q010.

### Q015

Reproduced on dev 0be6ccb (filed by Ethan's session 2026-11-11; HIGH PRIORITY, Ethan's decision):
- `nightshift/logs.py:50` (`log_variant`): `cap = date.fromisoformat(data_end_max or C.load()["explorer"]["data_end"])`.
  `C.load()` reads `config/night.yaml` from the checkout the explorer runs in, which is dev (night-explorer.md
  step 1 checks out origin/dev). A dev commit that moves `explorer.data_end` past 2019-12-31 would let the log
  accept variants on 2020-2026 data, the data held back for confirmatory tests (hard rule 4).
- `data_end_max` lets any caller replace the cap with a later date. No CLI flag passes it today, but nothing stops
  a later caller from loosening the cap.
- The cap is enforced only when a variant is logged. The explorer's own data reads are bounded by the agent's
  instructions (`.claude/agents/explorer.md`, `.loc[:"2019-12-31"]`), not by code. That is out of scope here and
  noted for Ethan.
Ethan (2026-11-11): the 2019-12-31 cutoff protects the 2020-26 test data, so it must come from main's protected
config/night.yaml, never from dev. **The night-explorer routine stays disabled until this item is merged into
dev.**
Depends on `nightshift.config.load_main` (PR #29 into main). Night-start merges main into dev before any worker
run, and the chain does not start if that merge fails, so the function is on dev before this item is worked.
Side effect of keeping the explorer disabled (for Ethan, not part of this item): `nightshift/guard.py`
`next_routine` alternates, so after a worker run it answers `night-explorer` while
`explorer.max_hypotheses_per_night` (3) is not used up. The explorer's trigger and its hourly fallback are
disabled, and the hourly night-worker fallback ends quietly when `guard next` does not say `night-worker`
(night-worker.md step 1). The chain therefore stalls after one worker run per night. Setting
`explorer.max_hypotheses_per_night: 0` on main makes `explorer_left` false, so `next` keeps answering
`night-worker`. With PR #29, the guard reads main's config fresh, so the change applies at the next run.
The Opposition (advisory, p=45). The reviewer could not read PR #29. Its main objection, that main's
config/night.yaml is unprotected and promotion would carry a loosened cutoff to main, is answered by PR #29: it adds
`/config/night.yaml` to CODEOWNERS and to `nightshift/protected.py` ALWAYS, so promote check (c) refuses a dev edit.
Points taken into the acceptance test: an unreadable cutoff gets its own exit code (2), so the explorer stops
instead of computing variants it cannot log (rule 6). Every failure prints "refused" (the CLI catches only
ValueError today). The existing log test must stub load_main. The no-C.load check is done by AST. If load_main is
missing, the item is blocked; a hand-written load_main on dev would conflict with PR #29 at night-start's merge.
Open for Ethan, not part of this item:
- logs.py itself runs from the dev checkout, so a dev edit to it would remove the check at once. Protection only
  gates promotion.
- The binding control on what data the explorer reads is the hardcoded `.loc[:"2019-12-31"]` in the protected
  `.claude/agents/explorer.md`; the log checks only a self-reported date.

### Q016

Filed by Ethan's session 2026-11-11 (Ethan's decision):
- `nightshift/queue.py` `auto_approve` only moves `proposed` items (to `approved` or `blocked`). No code ever
  moves a `blocked` item back. Q012 was set to `blocked` on 11 Nov, waiting for `nightshift.config.load_main`
  (PR #29) on dev. Once PR #29 lands, Q012 stays blocked until someone edits dev by hand, and sessions on main may
  not edit docs/queue.md (CLAUDE.md).
- Night-start already runs `python -m nightshift.queue auto-approve` in step 5 (`.claude/routines/night-start.md`,
  protected). A check made inside `auto_approve` therefore runs at every night-start with no change to the routine
  text.
Design constraint (hard rule 12, queue text is data): an `unblock_when` condition is read as data from a fixed
set of check kinds, for example `symbol:<module>:<name>` (the attribute exists, found by reading or parsing the
file's source on dev without importing or running it) and `commit:<sha>` (an ancestor of dev). It is never passed
to eval, exec, import or a shell. An unknown kind or a malformed condition leaves the item blocked and is reported.
Q012's condition: `symbol:nightshift.config:load_main`.
The Opposition (advisory, p=50), taken into the acceptance test:
- Merge rank undoes an unblock. nightshift.merge ranks blocked above approved and in-progress whatever the merge
  base says. After a refused promotion, main still has the old blocked row (equal to the base), and night-start
  would put an unblocked item back to blocked, so an in-progress item could be approved and implemented twice.
  This refines the rule set on 11 Nov (most advanced status wins): rank decides only when both sides changed the
  row.
- Where the condition lives. A 9th column would break the strict 8-cell parser in guard, morning, promote and
  merge, so the condition is an anchored line in the evidence section.
- Fire once. Only reviewed bug, data and lab items are eligible.
- Defined in code. A symbol must be a real definition (AST), not a stub name in a comment.
- No option injection through commit:<sha>.
- The no-eval guarantee is tested by patching builtins, not by grepping the source.

### Q017

Filed by Ethan's session 2026-11-11 (Ethan's decision; raised by The Opposition in its re-review of Q012):
- `nightshift/state.py` `acquire` (lines 71-82) stores the lock as `{routine, acquired_at, session}`. `release`
  (lines 85-99) copies `acquired_at` and `session` into the log entry. Neither records the run cap or the
  safe-mode flag in force for that run.
- After PR #29, the cap comes from main's config, fetched fresh at each `acquire`, so it can change during a
  night. The 11 Nov morning report said "0 of 12 runs" while main had safe mode on (cap 4). No record in
  `docs/agent-state.json` shows which cap applied to which run, so the morning report (Q012) can only show main's
  config at the time the report is written.
Fix direction: `acquire` stores `cap` and `safe_mode` (and the explorer model) in the lock, `release` copies them
into the log entry, and a stale-lock takeover entry carries them too. Older entries without these fields stay
valid. The morning report can then show the cap actually applied.
The Opposition (advisory, p=60): the guard enforces the cap with its own config read, separate from acquire's, so
after PR #29 a change on main between `guard check` and `state acquire` would leave a recorded cap that was never
applied. Acceptance changed so that acquire also refuses at the cap, which makes the value it records the last
cap that gated the run. `explorer_model` reflects config intent, not the model that ran, so it is recorded only on
explorer entries and labelled `explorer_model_config`. The 11 Nov night had no runs (the chain stopped at 22:41),
so per-run fields would not have helped that report. Depends on PR #29 (`load_main`, and acquire refusing when it
fails), which night-start brings into dev before any worker run.

### Q018

Filed 2026-11-11 by Ethan's session "N Janus C08" (Ethan asked for it in the queue, on dev). Reproduced from the
GitHub Actions run list (API `actions/workflows/<file>/runs`, event `schedule`), read 2026-11-11 03:10 UTC:

| workflow (cron, UTC) | scheduled runs: created_at (delay) |
|---|---|
| ledger-daily (52 5 / 22 9) | 6 Nov 13:15 (+7h23), 16:50 (+7h28); 7 Nov 11:56 (+6h04), 15:46 (+6h24); 8 Nov 12:14 (+6h22), 16:05 (+6h43); 9 Nov 14:25 (+8h33), 19:55 (+10h33); 10 Nov 13:48 (+7h56), 17:09 (+7h47) |
| elections-daily (41 6) | 5 Nov 14:57 (+8h16); 6 Nov 14:37 (+7h56); 7 Nov 13:33 (+6h52); 8 Nov 13:51 (+7h10); 9 Nov 16:51 (+10h10); 10 Nov 15:14 (+8h33) |
| ledger-pages (41 6) | the same day and minute as elections-daily each day (5-10 Nov, within 20 s) |
| ledger-watchdog (17 12) | 6 Nov 19:23 (+7h06); 7 Nov 17:44 (+5h27); 8 Nov 17:55 (+5h38); 9 Nov 22:20 (+10h03); 10 Nov 19:42 (+7h25) |

**What it is not:**
- **Not cron timing:** every cron is already off the hour (:52, :22, :41, :17), and all five scheduled workflows
  are late by similar amounts on the same days, ledger-daily or not.
- **Not runner queueing:** `run_started_at` equals `created_at` on every run, and the job starts 3 s after the run
  is created. For example, run 42861943209 was created 17:09:14 and the job started 17:09:17.
- **Not a wait step or the concurrency group:** its steps run back to back (marks 5 min, the rest about 2 min).
  The `ledger-intake` concurrency group cannot explain it: elections-daily, ledger-pages and ledger-watchdog are not
  in it and are just as late.
- **Not GitHub-side failure to run:** a `workflow_dispatch` started at once (run 42950449179, 2026-11-11 03:05:56).

**What it is:** GitHub creates this repository's `schedule` events 5.5-10.5 hours after their cron time. GitHub
documents that scheduled workflows can be delayed during periods of high load, and dropped. Its two daily
ledger-daily runs keep their 3.5-hour spacing, so each is delayed separately, not queued behind the other.

**Why it matters:**
- ledger-daily runs at about 12-20 UTC, so the morning app build (06:41 cron) shows the previous day's marks.
- FRED-style sources (published about 21 UTC) were two business days old at the 23:07 UTC Janus review. C09
  (2026-11-11) moved US10Y and GB10Y to faster sources, but the run time still decides how fresh every mark is.
- The 22:30-05:30 SGT night shift sees ledger-daily start inside its window (docs/agent-system.md inventory).

**Proposed fix (needs Ethan):**
- Hard rule 3: ledger-daily's workflow is an existing writer's.
- Hard rule 11: a new scheduled task is a settings change.
- So the night shift may not apply it: Needs Ethan.

The steps:
1. **Dispatch ledger-daily from a Claude Code scheduled task, not from cron.**
   - Scheduled tasks fire on time: the Janus quick-check records land within minutes of :15 and :45.
   - Add one task, "ledger-daily kick", that calls `workflow_dispatch` on `ledger-daily.yml` through the Claude
     GitHub App (the same call that started run 42950449179). It runs twice a day:
     - 06:07 UTC, its current role before the morning app build;
     - 22:07 UTC, after the US close and the day's official publications (Treasury par curve, ECB 16:00 CET
       reference rates, Bundesbank, BCB PTAX, Banxico FIX), an hour before the 23:07 Janus daily review.
   - The task only dispatches. It does not write files or run the guard.
   - It is not a Janus schedule (hard rule 14 covers creating Janus schedules).
2. **Keep both crons as backups.** ledger-daily is idempotent: marks merge per instrument and date, and runs share
   the `ledger-intake` concurrency group.
3. **Add a lateness line to the job summary:** `github.event.schedule` (or "dispatch") and minutes since the
   intended time. ledger-watchdog would open "[ALERT] ledger-daily late" when no ledger-daily run has started
   between 21:52 and 22:52 UTC by 22:55 UTC.

**Alternatives considered:**
- An external cron (for example cron-job.org) calling `repository_dispatch` needs a long-lived PAT stored outside
  GitHub: worse than the App-scoped dispatch.
- Moving the cron minutes does not help: the delay is platform-side and the same for every minute used.
- A self-hosted runner does not help either: it does not change when GitHub creates the schedule event.

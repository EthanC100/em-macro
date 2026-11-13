# Manhattan operations: design

Session 7M, branch `build/manhattan-ops`. Criteria and status: [../OPS_PROGRESS.md](../OPS_PROGRESS.md). The
private ledger: [LEDGER.md](LEDGER.md). The runner: [RUNNER.md](RUNNER.md). The blind generator:
[BLIND_GENERATOR.md](BLIND_GENERATOR.md). What only Ethan can do: [ETHAN_OPS_ACTIONS.md](ETHAN_OPS_ACTIONS.md).

The aim is the smallest system that lets Manhattan run its first genuine research cycle on **public** data while
every statistical claim stays switched off. Statistical claims stay gated: `manhattan/ops/promotion.py` refuses every
tier until Ethan adopts a validated protocol version.

## 1. Outcome blinding by access control

**The problem.** em-macro is public. Its files, git history, Actions logs, step summaries, artifacts and issues can
be read by anyone, including a generator session that has the web. A flag such as "do not read results/" is a
request, not a wall. So performance must never be written to em-macro in any form.

**The design.** Two stores with different access:

| store | who can read | who can write | holds |
|---|---|---|---|
| em-macro (public) | everyone | Ethan; sessions through the Claude GitHub App | specs, manifests, hashes, code, **operational health only** |
| `manhattan-ledger` (private, to be created by Ethan) | Ethan, the runner's deploy key | the runner's deploy key only | captures, registrations, screening and forward results, the runner's private log |

No Claude Code session is given `manhattan-ledger`: Ethan withholds the Claude GitHub App's access to it, and the
runner reaches it only through a deploy key held as an Actions secret (secrets are not readable by sessions and are
masked in logs).

**What may be public.** Only a health record (`manhattan/ops/blinding.py`): a fixed list of keys, each with a value
kind (integer, boolean, date, UTC time, a 40- or 64-character hash, a status word without dots or spaces). A float,
a free-text string or an unknown key is refused before anything is printed. That rules out a number with a decimal
point anywhere in public output. Exceptions are reported by stage and class name only.

| channel | what reaches it | how it is kept clean |
|---|---|---|
| repository tree and git history | nothing from the runner (permission `contents: read`) | the runner has no write access to em-macro |
| Actions log (stdout, stderr) | the health line | file descriptors 1 and 2 point at a private log while the runner works (`blinding.quiet`), so prints, warnings, subprocess output and tracebacks go private |
| step summary | the health table | `blinding.summary_markdown` checks the record first |
| failure issue | the health table | `runner issue-body`; a malformed record becomes a bare "failed" |
| artifacts | none | the workflow uploads none (a test reads the YAML) |
| caches | pip downloads only | no outcome is on disk outside `$RUNNER_TEMP/private`, which is removed at the end |
| exit status | pass or fail | operational |

**Brute-force resistance.** The runner publishes the private ledger's head hash in every health record (a public
anchor for tamper evidence). Each private record carries a 128-bit random nonce, so the head hash cannot be used to
confirm a guessed outcome by hashing candidates.

**Tested.** `tests/test_manhattan_ops_e2e.py` runs a synthetic batch end to end, including a run that fails with a
performance value in its exception message, then searches the public repository's tree and every git object, the
captured log, the step summary, the issue body, the runner's temporary directory outside `private/` and the
artifacts directory for every value the private ledger holds, in every rendering. It finds none. A second test plants
a value in each channel and shows the scanner finds it.

**Limits, stated plainly.**

- Ethan can read everything in the private ledger. Blinding of humans depends on his discipline.
- The specs are public, and so is the data. Anyone, a model with web access included, can recompute a public-data
  strategy's performance. The blinding protects Manhattan's own records; keeping a blind generator from recomputing
  them is the isolation kit's job (no network).
- Timing is visible: run durations, pass or fail, and how many observations were recorded. None of these depends on
  an outcome's value, but they are public.
- Exploration-role results (to 2019-12-31) are open by design in ARCHITECTURE §6; the screening the ops code runs on
  them is nonetheless recorded only in the private ledger, as asked. The freeze pull request carries each grid's
  effective variant count (a property of how variants move together, not of what they earned), rounded.

## 2. Freeze validity, separate from authorisation

Ethan's merge of a manifest pull request **authorises** a freeze. It does not certify timing.
`manhattan/ops/timing.py` certifies timing per prediction, mechanically:

- **Registration time** `R` is the later of GitHub's server-side merge time (the API's `merged_at`, not a commit
  date, which anyone can set) and a verified external witness of the manifest hash (OpenTimestamps by default). If
  either source is honest, the spec existed by `R`. Without a verified witness, a registration is `provisional`,
  carries evidential weight 0, and is re-assessed when the witness arrives; the new record is kept beside the old.
- **First eligible observation**: the first session close on the family's calendar, in the market's own time zone,
  strictly after `R` plus the execution lag in minutes, then moved forward by the execution lag in sessions.
  Calendars: US Federal Reserve (H.10 exchange rates, close taken as 17:00 New York, published the next session at
  16:15) and NYSE (16:00); weekends and rule-based holidays, Good Friday on the exchange only.
- **Prospective** only if, at `R`, the outcome window had not begun (its first close is after `R`) and nothing in it
  was observable (published after `R`). Ineligible reasons: `window_begun_at_registration`,
  `witness_after_window_start`, `first_observation_inside_execution_lag`, `declared_first_observation_not_a_session`,
  `data_cutoff_after_registration`, `data_cutoff_inside_outcome_window`. Ineligible predictions are recorded and
  tracked with weight 0, never dropped.

Each registration record holds the spec hash, `R`, both sources, the data cutoff, horizon, execution lag, the
declared and the computed first observation, the first close and its publication time, and the verdict. Tested edge
cases (`tests/test_manhattan_ops_timing.py`): a Saturday merge, Thanksgiving, Good Friday (exchange versus Fed), one
minute either side of the close, exactly at the close, the same UTC time either side of daylight saving, a value
published after the close, a late merge, a lag over a weekend, Veterans Day, a late witness, cutoffs.

## 3. Promotion is disabled in code

`promotion.promote` raises unless the protocol's SHA-256 is in `ADOPTED_PROTOCOLS` (empty) **and**
`claims.enabled` is true in `config/manhattan.yaml`. Each is a deliberate act by Ethan; neither alone is enough.

## 4. Variant limits and the compiler

Every varied grid parameter needs an economic reason and the range the mechanism implies (`justify.py`); the
mechanical critic (`critic_rules.py`) blocks an unjustified dimension, a value outside its range, a grid above 16
variants without a budget justification, missing timing fields and a spec that does not compile. The freeze tool
reports, per grid, the raw count, the Li-Ji effective count on exploration returns, and an approximate loss of power
from the search (single test versus the Šidák critical value at the effective count, at θ_min = 0.25 over a stated
window; an upper bound under those assumptions, not a property of SPA). Every variant is counted.

The compiler (`compiler.py`) turns a hypothesis with a structured `signal` (kinds: `tsmom`, `xs_momentum`,
`reversal`, `carry`, `calendar`, `event`, `buy_hold`) into engine strategies at the family's natural frequency
(`D`, `W`, `M`, `event`), with the family's sign, the universe, the cost model and the sizing rule. Interfaces stream
(executables are produced one at a time and counted without enumeration), so nothing in them stops at a million
executables; nothing has been optimised for that.

## 5. What is built, and what is not

Built and tested: everything above, the private ledger, the runner, the freeze tooling, the isolation kit and the
end-to-end proof. Not built: a real batch, a real hypothesis, any statistic beyond the variant report, the watchdog
for a silent runner (the failure issue covers a failed run; a run that never starts is only visible as
`missed_run` records on the next run, and in the Actions history), a public anchor file in em-macro, and the iMac
runner.

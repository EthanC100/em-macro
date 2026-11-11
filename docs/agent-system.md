# The night shift: autonomous overnight agents

Recorded 2026-11-09 (session "N Night shift setup"), built on main at a86c4bb, after chat 6's changes of the same
day (C05, K002, K003 and the salted commitments, the 7-day settlement re-request, T25-T26 Amendment 2 and its
recorded rerun). Nothing here changes those: where this design met them, main won (see "Adapted to main").

The night shift works from **22:30 to 05:30 Singapore time** (14:30-21:30 UTC) with no human input. It fixes
queued bugs and data problems, explores new ideas on pre-2020 data, runs a separate experimental paper book (the
Lab), and every morning either promotes the night's work to `main` through one checked pull request or explains
why not. A weekly brief goes out as a Gmail draft on Saturdays.

**Hard rules:** `CLAUDE.md`, "Night shift: hard rules". They override everything in this document.

---

## 1. Every writer to main (inventory)

Every one of these keeps working unchanged. "Identity" is who GitHub sees push to `main`.

### GitHub Actions workflows

| workflow (file) | schedule | identity on main | writes on main | also writes |
|---|---|---|---|---|
| **ledger-daily** (`.github/workflows/ledger-daily.yml`) | 05:52 and 09:22 UTC daily, and by hand. **Actually starts 7-11 hours late**: runs 5-10 started 11:56-16:50 UTC (19:56-00:50 Singapore), today's at 14:25 UTC, so it often runs **inside the night window** | `GITHUB_TOKEN` (github-actions[bot]) | `data/ledger/` marks, decisions, forecasts, derivative_pnl, automation_log, api_log, postmortems, reports, changes.json, state.json, stress*.json; `data/raw/bist`, `data/raw/bondspot`; `results/shadows/` (from go-live). Then through `scripts/ledger_commit.sh`: `data/janus/`, `data/ledger/seals.jsonl` and the other ledger_commit paths | em-macro-data `ledger/`, `databento/shadows`, `shadows` with secret `EM_MACRO_DATA_TOKEN`; Databento API (US$1/day cap) |
| **ledger-intake** (`ledger-intake.yml`) | on issues opened/edited/reopened (Ledger forms); from Q022 also `workflow_dispatch` (input `issue`) from ledger-daily's sweep of forms with no intake comment after 30 minutes | `GITHUB_TOKEN` | the entry's file under `data/ledger/` and its seal, both through ledger_commit.sh on a fresh main (Q022: the id is re-allocated if the push is rejected). Its own concurrency group per issue; ledger-daily, private-commitments and shadows-setup share `ledger-writers` | issue comments |
| **systematic-monthly** (`systematic.yml`) | 07:23 UTC on the 3rd (the rebalance); Mon/Thu 06:37 keep-cache (no push) | `GITHUB_TOKEN` (plain `git push`, no retry) | `results/systematic/` (positions, paper_pnl, rebalance_log, adjustments, overrides_log, `d005/` from the D005 step), `results/systematic_v1.1/`, `results/live_compare/`, `data/processed/`, `data/raw/{bondspot,bist,imf_weo}`, coverage reports, `results/screener/`, `data/ledger/reports`, changes.json, state.json | alert issues |
| **ledger-screener** (`ledger-screener.yml`) | by hand | `GITHUB_TOKEN` | `results/screener/`, `data/ledger/reports` | |
| **elections-daily** (`elections-daily.yml`) | 06:41 UTC daily | `GITHUB_TOKEN` | `data/elections/`, `docs/elections/` | alert issues |
| **elections-weekly** (`elections-weekly.yml`) | Mondays 06:17 UTC | `GITHUB_TOKEN` | `data/elections/`, `docs/elections/` | |
| **shadows-setup** (`shadows-setup.yml`) | by hand (run #3 used; Amendment 2 record mode remains) | `GITHUB_TOKEN` | `results/shadows/` (GO_LIVE.json, prelive files) | em-macro-data with `EM_MACRO_DATA_TOKEN` |
| **private-commitments** (`private-commitments.yml`) | by hand | `GITHUB_TOKEN` | `data/ledger/derivatives.csv`, `data/ledger/seals.jsonl` (K003) | em-macro-data `ledger/commitments.jsonl` (salts) |
| **v1-rules-monitor** (`v1-rules-monitor.yml`, D004) | after every successful systematic-monthly run (`workflow_run`), and by hand | `GITHUB_TOKEN` (retries on a rejected push) | `data/ledger/v1_rules.json`, `data/ledger/v1_rules_history.csv` only (flags; never exposure, never frozen v1.0 files) | dispatches ledger-pages |
| **ledger-pages** (`ledger-pages.yml`) | every push to main, 06:41 UTC, by hand, dispatched by the others | none (no commit) | deploys GitHub Pages only | |
| ledger-watchdog (`ledger-watchdog.yml`) | 12:17 UTC | none (read only) | alert issues only | |

### Claude Code scheduled tasks (routines) on this account (list read 2026-11-09)

| task (prompt source) | schedule | identity on main | writes | model / effort |
|---|---|---|---|---|
| **Janus Quick Check** (trig_01Sxfs75…; `docs/janus/quick_check.md`) | hourly at :15, every day | **Ethan's GitHub user via the Claude GitHub App** (commit author "Claude <noreply@anthropic.com>") | `data/janus/records.jsonl` (+ seals) through `scripts/janus_commit.sh` | model not set (account default); every one of the 151 check records says `claude-sonnet-5-5`. Effort: not shown by the API (default) |
| **Janus Quick Check 2** (trig_01AqFEVG…) | hourly at :45, every day | same | same | same |
| **Janus Daily Review** (trig_01WFz73C…; `docs/janus/daily_review.md`) | 07:07 Singapore daily (23:07 UTC = 18:07 New York) | same | `data/janus/`, `data/ledger/postmortems`, seals | not set; records say `claude-sonnet-5-5` (The Opposition as a subagent of the same model). Effort: default |
| Horizon Daily Briefing | 09:34 Singapore daily | none: writes a Claude Docs document, no git push | | not set |
| Horizon Weekly Brief (the "weekly review") | Saturdays 18:00 Singapore | none (Claude Docs) | | not set |
| Month-ahead report | 28th, 21:00 Singapore | none (Claude Docs) | | not set |
| Ledger forecast resolver (`docs/ledger/forecast_resolver.md`) | documented as a daily task, **but not on the account's task list** (`docs/todo.md`: "Create the scheduled tasks", unticked) | would be Ethan via the Claude App | `data/ledger/forecasts.csv`, seals via ledger_commit.sh | — |
| Ledger monthly letters (`docs/letters/monthly_letters.md`) | documented for the 3rd-6th, **not on the task list** | same | letters via ledger_commit.sh | — |
| **ledger-daily kick** (trig_01Ci634N…, added 2026-11-11 for Q018, approved by Ethan) | **06:07 and 22:07 UTC** daily (`7 6,22 * * *`) | none: no commit; it dispatches `ledger-daily.yml` on main through the Claude GitHub App (`workflow_dispatch`) | nothing (dispatch only) | `claude-sonnet-5-5`. Fires into one standing session with em-macro attached (session_01Ayx8qcPWT8…, "ledger-daily kick (Q018)"), whose system prompt allows only the dispatch and a run-list check. Why: GitHub creates this repository's schedule events 5.5-10.5 hours late (Q018), so ledger-daily's crons are backups. Verified 2026-11-11: fired 06:41:54 UTC, run 42974261471 created 06:42:02 |

### Interactive and manual writers

| writer | identity on main | writes |
|---|---|---|
| **Ledger clerk** (pasted `DECISION RECORD` / `FORECAST` / `RESOLVE` blocks in any Claude Code session, `docs/ledger/clerk.md`) | Ethan via the Claude GitHub App | decisions, forecasts, derivatives, seals through ledger_commit.sh |
| Build sessions (e.g. "chat 6" today: C05, K002, settlements, Amendment 2) | Ethan via the Claude GitHub App: direct pushes to main, or branches merged by Ethan | any file |
| Ethan (web UI merges, uploads) | EthanC100 | any file |

**Not found:** no personal access token pushes to `em-macro` in any workflow (the only PAT-like secret is
`EM_MACRO_DATA_TOKEN`, used for em-macro-data). If a token named "horizons-data-push" exists, nothing in this
repository uses it to push here; it would act as EthanC100 if it did. Deploy keys cannot be listed from a session
(Settings > Deploy keys needs admin): none is referenced in the repository.

## 2. The new routines, next to the existing writers

| routine (`.claude/routines/`) | trigger (Singapore time) | model / effort | subagents | writes |
|---|---|---|---|---|
| night-start.md | 22:30 daily | Sonnet 5.5 / medium | triage (Sonnet 5.5, medium), opposition (Opus 5.5, high) | `dev`: merge of main; queue, state, calibration |
| night-worker.md | API trigger (chain) + hourly :35, 22:35-04:35 (fallback) | Sonnet 5.5 / medium | implementer, opposition (Opus 5.5, high) | `night/<Qid>` branch + PR into dev; queue, state |
| night-explorer.md | API trigger (chain) + hourly :05, 23:05-04:05 (fallback) | Opus 5.5 / high (Sonnet / medium in safe mode) | explorer (Opus 5.5, high), opposition | `dev`: exploration log, sleeves, prereg drafts |
| pr-review.md | GitHub `pull_request.opened`, base `dev` | Sonnet 5.5 / medium | opposition | merges `night/*` PRs into dev; queue |
| promote.md | 05:30 and 06:30 | Sonnet 5.5 / medium | — | PR dev -> main (auto-merge) or nothing; `results/night/promote/` on dev |
| morning-report.md | API trigger from promote + 06:50 (fallback) | Sonnet 5.5 / medium | reporter (Sonnet 5.5, medium) | `results/night/morning/` on dev |
| weekly-brief.md | Saturdays 08:00 | Sonnet 5.5 / medium | reporter | `briefs/` on dev; Gmail draft |

Subagents are in `.claude/agents/` with `model:` and `effort:` in their frontmatter (both keys are documented
for Claude Code subagents). **Effort for a routine** is chosen in the routine's model selector at
claude.ai/code/routines; it cannot be set from a file or from the scheduled-task API, so the setup steps below
say what to pick.

**Never at the same time as an existing writer.** `python -m nightshift.guard` reads the public Actions API and
refuses to start while ledger-daily, systematic-monthly, ledger-intake, shadows-setup, private-commitments or
ledger-screener is queued or running (it also refuses when the API cannot be read), and inside fixed windows: the
Janus daily review (23:00-23:45 UTC) and the 3rd-of-month rebalance (07:15-09:30 UTC). Night work never touches
main's files directly, so the Janus quick checks (every 30 minutes, all night) never collide with it.

## 3. How a night runs

1. **22:30 night-start**: guard; merge `origin/main` into `dev` (a conflict stops the night, never resolved);
   triage files reproducible findings in `docs/queue.md`; The Opposition reviews every unreviewed bug/data/lab
   item; `nightshift.queue auto-approve`; fires the next routine.
2. **Chain**: night-worker and night-explorer alternate (`python -m nightshift.guard next`); the explorer runs when
   the approved queue is empty (at most 3 hypotheses a night). Each run takes the lock (stale after 2 h), counts
   one run, and fires the next routine's API trigger (`scripts/night_fire.sh`, URL and token from environment
   variables). The chain stops when nothing is left, at the cap (12; 4 in safe mode), or after 05:00.
3. **Worker**: one approved item per run; the implementer branches `night/<Qid>` off dev, writes a test that fails
   first, fixes, runs the suite, opens a PR into dev. pr-review (GitHub trigger) runs the tests, the protected-path
   check and The Opposition, and merges into dev unless something fails or The Opposition blocks.
4. **05:30 promote**: `python -m nightshift.promote` on the exact tree the PR would produce (main merged with dev):
   (d) conflict-free, (c) no protected path changed on dev, (a) the full suite passes, (b) the Ledger rebuilt from
   scratch on main and on that tree with the same `--today` and the same em-macro-data snapshot matches exactly
   except for app files the night's merged items list under "ledger diff", and both audit chains verify. All pass:
   a PR dev -> main with auto-merge. Any fails: no PR, reasons in the morning report.
5. **Morning report** (one phone screen): Promoted to main, Merged into dev, Failed or empty runs (verified against
   dev and the logs, not the run status), Janus (C05 compliance and positions, read from the existing reviews and
   quick checks), Lab sleeves, Explorer findings, Pre-registrations awaiting Ethan, Usage, Needs Ethan (max 3).

State lives in `docs/agent-state.json` (lock, night, run counter, per-run log), written only through
`python -m nightshift.state` inside `scripts/night_commit.sh`, which commits only the night shift's own paths and
only to dev (it refuses main).

**API triggers from a cloud session:** checked here: `api.anthropic.com` is reachable from this environment (an
unauthenticated POST to the fire endpoint answers 401, i.e. it is reachable and needs the token). The chain
therefore uses API triggers; the hourly schedules of night-worker and night-explorer are the documented fallback
if a fire fails or the token is missing (`night_fire.sh` exits 6 and says so).

## 4. Queue and The Opposition

`docs/queue.md`: id, type (bug/data/research/lab), status (proposed/approved/in-progress/done/blocked), acceptance
test, branch/PR, opposition, ledger diff, and an evidence section per item. bug, data and lab items become
`approved` automatically once The Opposition has reviewed them and found no hard-rule violation; research items
needing a pre-registration are drafted for Ethan and wait. The Opposition may block only for (a) breaking the live
system or Ledger, (b) protected paths, (c) look-ahead or 2020+ returns in exploration, (d) leaking licensed data,
salts or secrets, (e) unlogged variants. Its probability that each thing works goes to
`results/opposition/calibration.csv` for later scoring.

(Janus also has "The Opposition" inside its daily review, per position. That one is unchanged and separate.)

## 5. The Lab ("Lab - experimental")

A separate paper book with its own page and chart in the Ledger app (More > Lab - experimental), never read by my
book, the algorithm, Janus, the T25-T26 shadows or the fund (`tests/test_nightshift.py` checks the imports).
One sleeve per idea in `lab/sleeves/<id>.yaml`, frozen at launch by its SHA-256 in `lab/registry.csv`; changing a
sleeve means launching a new one. 0.5% paper risk per sleeve, 5% for the Lab, retirement 6 months by default
(at most 12). Fills at the first first-hand daily public mark on or after launch; closes at the stop or the
retirement date. Explorer nominations launch automatically once The Opposition has written its case and the sleeve
passes `python -m lab.book validate`. Public daily marks only: no settlements.

## 6. Janus: why it has no trades (diagnosis, 2026-11-09)

Evidence from `data/janus/records.jsonl` (162 records), the scheduled-task list and `ledger/janus.py` on a86c4bb:

1. **No daily review has run since C05 took effect.** C05 was committed at 03:09 UTC on 9 Nov, effective "the next
   Janus daily review (9 November 2026)". The Janus Daily Review task fires at 07:07 Singapore = 23:07 UTC; its
   last run was 8 Nov 23:08 UTC (records 131-132), before C05; the next is **9 Nov 23:07 UTC**. So far Janus has
   had zero reviews under C05: no trades is expected, not a malfunction.
2. **Every review before C05 would fail it.** Five reviews (records 3, 6, 32, 82, 132): all `no_trade` at 0% at risk
   with a general reason ("No position where I can defend an edge above 50%..."), none with `below_budget`; three of
   the four session reviews (6 Nov 12:11, 7 Nov, 8 Nov) had empty `sources_read`. All five session-era runs used
   `claude-sonnet-5-5` (the task has no model set) and finished in about a minute (8 Nov: 23:08:06 to 23:09:15).
3. **The quick-check flags fire.** All 22 check records since C05 carry both flags: "daily review 2026-11-08 failed:
   empty sources_read (before the 2026-11-09 research rule)" and "0.00% at risk, below the 3% budget without a
   current specific reason".
4. **No mark or data problem blocks it.** Public marks run to 6 Nov (GB10Y 4 Nov, US10Y and JP10Y 5 Nov: source
   lags). Futures settlements were available to the reviews through the read-only clone (records 81 and 131 say
   so). ledger-daily starts late but well before 23:07 UTC, and fills happen at the next ledger-daily after a
   review. (In a session without em-macro-data attached, all 11 futures markets show no mark; the Janus tasks have
   had it.)
5. **The code enforces C05.** `ledger/janus.py` `_check_mandate` runs on every `daily_review` proposal (line 868):
   empty `sources_read` is rejected; below 3% needs a specific `below_budget` (generic reasons rejected by regex,
   `until` at most 30 days); weekend/holiday `deferred_ideas`; the quick check's `mandate_flags`. Tests in
   `tests/test_janus.py`. Because each position is capped at 2%, 3% at risk already implies at least 2 positions.
6. **One gap where C05 and the code differ:** C05 says a review with empty `sources_read` "counts as failed, and the
   quick check flags it". In code a rejected proposal appends nothing, so the quick check keeps reporting the
   previous review and flags "no daily review" only after a day (queue item Q004, blocked: recording a rejection
   changes the Janus writer path; Needs Ethan). Closed on 2026-11-10 by config change C06: a rejected daily review
   now writes a failed-review record that the quick check flags the same day.

Where C05 is silent and nothing was invented: the model and effort of the Janus tasks; whether "normally 2-6
positions" means an enforced upper bound (only the existing 8-position limit is enforced); what happens if the
daily review task fails to start. **The morning report reads the existing daily review and quick checks; no new
Janus schedule was created.**

## 7. Protected paths

The block in `.github/CODEOWNERS` (EthanC100 as required code owner) and promotion check (c); every path was found
on main (the test checks each exists):

| category | exact paths |
|---|---|
| frozen v1.0 (`docs/v1.0_freeze.md` hash tables) | `em_macro/systematic.py`, `em_macro/risk_model.py`, `em_macro/carry.py`, `em_macro/sources.py`, `em_macro/panel_sources.py`, `results/systematic/fit/`, `results/risk_model/fit/frozen_params.json`, `results/systematic/test/`, `docs/v1.0_freeze.md`; tag `v1.0-frozen` (7886867) |
| frozen v1.1 (`docs/v1.1_freeze.md` hash tables) | `em_macro/systematic_v11.py`, `em_macro/t18_rebal.py`, `em_macro/tstrend.py`, `em_macro/t1619.py`, `em_macro/t01.py`, `em_macro/holdout.py`, `em_macro/verify_v1.py`, `em_macro/cost_audit.py`, `results/T16-T19/performance.csv`, `results/T16-T19/monthly_net.csv`, `results/cost_audit/cost_estimates.csv`, `results/systematic_v1.1/freeze/`, `docs/v1.1_freeze.md`; tag `v1.1-frozen` (ffdb5c8) |
| T25-T26 shadows | `docs/prereg/T25-T26_live_shadows.md` (pre-registration with Amendments 1 and 2), `results/shadows/GO_LIVE.json`, `results/shadows/prelive.json`, `results/shadows/prelive_amendment2.json`, `results/T25-T26/` (the availability evidence the pre-registration cites) |
| pre-registrations | `docs/prereg/` |
| corrections log (K001-K003) | `data/ledger/seals.jsonl` (the corrections are records in the audit chain) |
| config changes, commitments, trials | `docs/config_changes.md`, `ledger/commitments.py`, `trials.csv` |
| D005 volatility floor (supersedes D004 rule 4) | `config/v1_managed_fx.csv` (managed-currency list), `em_macro/d005.py`, `em_macro/d005_fallback.py` (the override and its fail-safe); all three also always protected in `nightshift/protected.py` |
| the agents' own rules and switches | `.claude/`, `config/night.yaml` (also always protected in `nightshift/protected.py`), `.github/CODEOWNERS`, `docs/rulesets/` |

Tags cannot be covered by CODEOWNERS: `docs/rulesets/frozen-tags.json` blocks updating or deleting both tags.
`data/processed/*.csv` (hashed v1.0 inputs) are not protected: the monthly workflow rewrites them by design, the
frozen snapshots are the copies at the tag, and the night shift may not edit writer-owned data anyway (rule 3).
`results/shadows/` other than the three files stays writable by ledger-daily (live shadow results from 4 Dec).

## 8. Ruleset for main (design only; Ethan applies it)

`docs/rulesets/main.json`: PR required on the default branch, **0 approvals**, **code-owner review** (so only PRs
touching the CODEOWNERS block need Ethan), no force push, no deletion. Bypass ("always"):
- **Repository role: admin** (`actor_id` 5): covers every writer that pushes as EthanC100: the Janus tasks, the
  clerk and build sessions (the Claude GitHub App acting for the user: "Anything a scheduled task does through your
  connected GitHub identity appears as you", code.claude.com/docs/en/routines), and Ethan himself.
- **GitHub App: GitHub Actions** (`Integration`, `actor_id` 15368): covers every workflow pushing with
  `GITHUB_TOKEN` ("The GITHUB_TOKEN secret is a GitHub App installation access token", GitHub docs).

Checked against GitHub's documentation: rulesets are available on public repositories with GitHub Free; bypass
can be granted to "Repository admins…", "The maintain or write role…", "Teams…", "GitHub Apps" and "Dependabot"
(no individual users or deploy keys in the UI list; REST also accepts `DeployKey` and `User`). Not documented:
the admin role's id 5 (read it back after creating the ruleset in the UI), and whether the GitHub Actions app can
be picked in the bypass list. **If it cannot, every workflow above loses its push to main**: apply the ruleset,
then run `ledger-daily` by hand at once and watch its commit step; if the push is refused, set the ruleset to
Disabled and see Needs Ethan.

`docs/rulesets/frozen-tags.json`: no update, deletion or force push of `v1.0-frozen` and `v1.1-frozen`, no bypass.

**Phone steps** (GitHub Mobile has no ruleset screens; use the browser in desktop mode):
1. github.com/EthanC100/em-macro > Settings > General > Pull Requests: tick **Allow auto-merge**.
2. Settings > Rules > Rulesets > **New ruleset > Import a ruleset**, choose `docs/rulesets/main.json` (download it
   from the repository first: open the file, "…" > Download). Check that the bypass list shows **Repository admin**
   and **GitHub Actions** (add them with "Add bypass" if the import dropped them), then **Create**.
3. Same for `docs/rulesets/frozen-tags.json`.
4. Actions > ledger-daily > Run workflow (main). Confirm it pushed (or said "nothing to commit"). If its commit
   step failed with a rule violation, open the ruleset and set Enforcement to **Disabled**.

### The identity finding (needs a decision)

The night agents run as Claude Code routines, so they push **as EthanC100 through the Claude GitHub App**, exactly
like the **Janus Quick Check, Janus Quick Check 2 and Janus Daily Review** tasks, the **Ledger clerk** and every
build session (and the forecast resolver and letters tasks once created). GitHub cannot tell them apart: the admin
bypass that lets Janus and the clerk push straight to main lets the night shift do so too. Inside these cloud
sessions a different token cannot be used either: the git proxy replaces any credential a client sends
(`docs/janus/daily_review.md`), so "give the night shift its own token" is not available from a routine. The
ruleset therefore stops the night shift only by convention (CLAUDE.md rule 1, `night_commit.sh` refusing main).
Options are listed under Needs Ethan; nothing was guessed or applied.

## 9. Weekly brief

Saturdays 08:00 Singapore (`weekly-brief.md`), built on the week's weekly review; beginner-readable; byline "Ethan
Cukierman, Horizons" in plain text; every market level carries two public sources from different sites whose
values agree, and is written into the text only as a checked placeholder (`nightshift/brief.py` refuses
hand-typed figures and the words settlement, Databento, Norgate); unconfirmed levels are flagged "(unverified)" or
dropped. Output `briefs/YYYY-MM-DD.pdf` (+ `.txt`) and a Gmail draft to the list. `config/brief.yaml`:
`auto_send: false`.

**To send automatically later** (`auto_send: true`): an account with a mailing service that has a send API (for
example Buttondown or Mailchimp), the list imported there, and its API key stored as the environment variable
`BRIEF_MAILER_API_KEY` in the weekly-brief routine's cloud environment. Not created here.

## 10. Usage budget (estimate)

Assumptions: Opus 5.5 costs 2x Sonnet 5.5 per token ($4/$20 against $2/$10 per million input/output tokens);
plan usage tracks token cost; high effort uses about 1.5x the tokens of medium. **1 unit = one Janus quick check**
(Sonnet 5.5, about 4.5 minutes: the 13:46-13:50 UTC run today). Per-run sizes are estimates from the work each
does, not measurements.

| job | model | runs/week | units/run | units/week | share at cap | share, realistic |
|---|---|---|---|---|---|---|
| Janus quick checks (2 tasks, hourly, every day) | Sonnet 5.5 (default) | 336 | 1 | 336 | 16% | 41% |
| Janus daily review (with C05 research + The Opposition) | Sonnet 5.5 (default) | 7 | 8 | 56 | 3% | 7% |
| night-start (triage + Opposition on ~4 items) | Sonnet orchestrator, Sonnet triage, Opus Opposition | 7 | 17 | 119 | 6% | 15% |
| night-worker at the cap (9 a night: implementer + Opposition) | Sonnet orchestrator, Opus high subagents | 63 | 13.5 | 851 | 41% | — |
| pr-review (one per worker PR) | Sonnet + Opus Opposition | 63 | 5 | 315 | 15% | — |
| night-explorer at the cap (3 a night) | Opus 5.5 high + Opposition | 21 | 13 | 273 | 13% | — |
| night chain, realistic (2 worker PRs, 1 explorer, 1 empty a night) | mixed | 28 | | ~250 | | 30% |
| promote + morning report | Sonnet 5.5 | 14 | 2.5 | 35 | 2% | 4% |
| weekly brief | Sonnet 5.5 | 1 | 6 | 6 | 0.3% | 0.7% |
| other Claude tasks (daily briefing 7, weekly review 1, month-ahead) | default | ~8 | 2-4 | ~20 | 1% | 2% |
| ledger-daily, intake, systematic, elections, pages | GitHub Actions, no Claude | — | 0 | 0 | 0 | 0 |
| **total** | | | | **~2,010 at cap / ~820 realistic** | | |

Checked against Anthropic's documentation (code.claude.com/docs/en/routines): routines "draw down subscription
usage the same way interactive sessions do"; per-plan daily run counts are not documented; the documented caps are
hourly: 100 scheduled runs per account, 100 API fires per account, 30 "Run now"+API fires per task, none with
overage. This system's peak is about 6 runs an hour (2 quick checks, ~3 chain runs, pr-review), far under those.
**The risk is the plan's usage limits, not run counts**: at the cap the night shift is about 80% of the week's
usage (about 4x the Janus load). Interactive sessions (like this one) come on top and are not estimated.
- **Safe mode** (`config/night.yaml` `safe_mode.enabled: true`, set on main): cap 4, explorer and its subagent on
  Sonnet 5.5 medium. Roughly 1,000 units a week less at the cap. The guard, promote and state read main's copy,
  fetched fresh on every run, so it applies at the next run without waiting for night-start's merge into dev; if
  main's copy cannot be fetched or parsed, nothing starts (fail safe).
- Janus's quick checks and reviews run on **Sonnet**, not Opus, so no model change is recommended. They run every
  hour of every day (336 runs/week), including weekends and nights when no Janus market trades; that is their
  existing schedule and C05 is not changed here.

## 11. One-time setup (Ethan, in order)

1. **Claude GitHub App** on EthanC100/em-macro (and read access to em-macro-data for the promote rebuild):
   github.com/settings/installations > Claude > Repository access. Already installed for em-macro (this session
   pushes through it).
2. **Merge this PR** (it adds `.claude/`, which only Ethan should approve), then let `dev` exist: the dry run
   created it; if it is missing, create it from main.
3. **Apply the rulesets** (section 8 phone steps), then the ledger-daily test run.
4. **Routines** at claude.ai/code/routines. The seven tasks were created from this session through the
   scheduled-task API and **disabled straight away** (created 14:56 UTC, disabled 14:57 UTC, before any could fire),
   with the schedules, one-line prompts and models below. What the API could not set, so you set it in the UI:
   **the repository** (they were created with no repository attached: add EthanC100/em-macro, and em-macro-data
   read-only), **effort**, **connectors** (refused for this organisation through the API: add GitHub where listed
   and Gmail on weekly-brief), the **API triggers** and the **GitHub trigger** (not available from the API), and
   "allow pushes to any branch". Then enable them after steps 2-3. Ids: night-start trig_01NmjpBKMbVrzBq2JbD92uJn,
   night-worker trig_01BVzWxckZiRAXYo1vdQReJq, night-explorer trig_01UQxVUME1DHW9Qz83tiVSiz, pr-review
   trig_01MjBsxNX2nQk6US3Fnfpqp6, promote trig_01WPa6MSaCJwziF6byaUS84z, morning-report trig_01Q21bwRJnYg8XRJQqrPUsvg
   (push notification on), weekly-brief trig_01LXiKzH3ctXPHnkJr1tcQCd.

   | name | prompt (one line) | model | effort | repository | environment | connectors | trigger |
   |---|---|---|---|---|---|---|---|
   | Night shift: night-start | Follow .claude/routines/night-start.md | Sonnet 5.5 | Medium | EthanC100/em-macro (+ em-macro-data read) | the Janus environment (same as the Janus tasks) | none | schedule 22:30 Asia/Singapore daily |
   | Night shift: night-worker | Follow .claude/routines/night-worker.md | Sonnet 5.5 | Medium | same | same | GitHub | API trigger + schedule hourly at :35, 22:35-04:35 SGT (`35 14-20 * * *` UTC) |
   | Night shift: night-explorer | Follow .claude/routines/night-explorer.md | Opus 5.5 | High | same | same | none | API trigger + schedule hourly at :05, 23:05-04:05 SGT (`5 15-20 * * *` UTC) |
   | Night shift: pr-review | Follow .claude/routines/pr-review.md | Sonnet 5.5 | Medium | same | same | GitHub | GitHub event: Pull request opened, base branch = dev |
   | Night shift: promote | Follow .claude/routines/promote.md | Sonnet 5.5 | Medium | same | same | GitHub | API trigger + schedule 05:30 and 06:30 SGT |
   | Night shift: morning-report | Follow .claude/routines/morning-report.md | Sonnet 5.5 | Medium | same | same | none; push notification on | API trigger + schedule 06:50 SGT |
   | Night shift: weekly-brief | Follow .claude/routines/weekly-brief.md | Sonnet 5.5 | Medium | same | same | Gmail (and Claude Docs to read the weekly review) | schedule Saturdays 08:00 SGT |

   Each routine must be allowed to push to non-`claude/` branches (`dev`, `night/*`); `main` is refused by the
   scripts, not by the routine settings.
5. **API trigger tokens**: for night-worker, night-explorer, promote and morning-report, add an API trigger, copy
   its URL and token (shown once) and store them as environment variables of the environment the routines use:
   `NIGHT_WORKER_FIRE_URL`/`_TOKEN`, `NIGHT_EXPLORER_FIRE_URL`/`_TOKEN`, `NIGHT_PROMOTE_FIRE_URL`/`_TOKEN`,
   `NIGHT_MORNING_FIRE_URL`/`_TOKEN`. Never in the repository.
6. **Gmail** connector on the weekly-brief routine; set `delivery.mailing_list` in `config/brief.yaml`.

## Adapted to main

- "The Opposition" already exists inside Janus's daily review (per position); the night shift's Opposition is a
  separate subagent and does not replace or touch it.
- The corrections log is not a separate file: K001-K003 are records in `data/ledger/seals.jsonl`, so that file is
  the protected path. It stays writable by ledger_commit.sh and the workflows (they push directly).
- The private store is read through the Janus CLI's read-only clone; the promote rebuild uses one path for both
  builds and records its commit before and after, so the 7-day settlement re-request cannot create a difference.
- The promotion compares main with **main merged with dev** (the tree the PR produces), not dev alone, because
  main keeps moving all night (Janus checks every 30 minutes).
- ledger-daily runs late into the night window, so the guard checks the Actions API instead of trusting cron times.

## Dry run (2026-11-09, 22:52-23:25 Singapore, real time, in the setup session)

| step | what happened | where |
|---|---|---|
| night-start | guard: go (22:52 SGT, no busy writer). `dev` created from this branch and synced with main 3e4059a (clean merge). Triage (Sonnet) returned two findings; both checked and filed as Q005 (ES-DE spread pairs legs from different days: 57.4bp recorded vs 52.4bp on one close) and Q006 (a monthly-panel fallback dated 30 Nov replaced CLP's 6 Nov daily mark). The Opposition (Opus): Q003 80%, Q005 55%, Q006 50%, no block; Q005/Q006 acceptance tests tightened from its concerns. Auto-approved Q003, Q005, Q006 | dev f0f206f |
| night-worker run 1 | lock taken; Q003 in progress; implementer (Opus) wrote `tests/test_q003_todo_counts.py` (failed: "says 21 of 28; the registry has 19 of 23"), fixed the line, suite 467 passed; PR #27 into dev. pr-review: clean merge onto dev, no protected path, 467 passed; The Opposition advisory 80% with one concern (a doc-prose test can gate systematic-monthly's commit), filed as Q007 and added to the implementer's and pr-review's rules. Merged into dev; Q003 done; lock released (run 1 of 12). Chain then stopped by hand: guard said night-explorer | PR #27, dev 2317609, d7339d3 |
| Janus diagnosis | section 6 above | |
| promote, check only | real: **refused** on (c) (dev carries this PR's own `.claude/`, CODEOWNERS and rulesets) and (b) (`app.js`, `lab.json`: the Lab page is not on main yet); (d) clean, (a) 467 passed, same em-macro-data snapshot on both builds, both chains verify. As if this PR were merged (base = main merged with this branch, local only): **all pass**, the only Ledger difference `todo.json`, declared by Q003. Found and fixed on the way: merged items are now only `Merge Qnnn` commits | `results/night/promote/2026-11-10*.json` on dev |
| morning report | one screen, real data | `results/night/morning/2026-11-10.md` on dev |
| routines | the seven created through the scheduled-task API and disabled within a minute, before any fired; models set | section 11 |

Not exercised: the API-trigger chain itself (no trigger tokens exist yet; `night_fire.sh` exits 6 without them and the hourly schedules take over), night-explorer and a Lab launch (outside the requested dry run), the weekly brief's Gmail draft (no Gmail connector in this session; the PDF renderer is tested).

# Exploration data: the loader, the extract and the explorer's sandbox (Q019)

Recorded 2026-11-12 by Ethan's session "N Explorer sandbox (Q019)". The explorer (night shift) may study data up to
**2019-12-31** only (`explorer.data_end` in main's `config/night.yaml`; hard rule 4). Before Q019 that was prose: the
explorer had Read and Bash over a checkout whose `data/`, `results/`, `trials.csv`, `docs/prereg/`, `README.md` and
`tests/fixtures/live/` hold 2020-2026 series and out-of-sample results. Q019 replaces the prose with code. The
explorer stays **off** until main has everything below and Ethan applies the routine change in section 5
(`max_hypotheses_per_night: 0` on main, and the gate in section 3).

## 1. What lives where

| what | where | public? | protected |
|---|---|---|---|
| allowlist, licence basis, exclusions, the extract's sha256, store path and commit | `config/exploration_manifest.json` | yes (hashes and metadata only) | CODEOWNERS + `nightshift/protected.py` |
| the extract: `date,series,value`, 26 series, 97,257 rows, 2005-01-03..2019-12-31 | em-macro-data `exploration/v1/extract.csv` (commit `043ff30`) | no | the sha256 on main: any edit is refused |
| builder, loader, gate | `nightshift/explore_data.py` | yes | CODEOWNERS + protected.py |
| sandbox create/collect | `nightshift/explore_sandbox.py` | yes | CODEOWNERS + protected.py |
| variant log and its cutoff check | `nightshift/logs.py` | yes | CODEOWNERS + protected.py |

**Sources.** One file, `data/processed/daily_panel.csv` (em_macro/build_data.py: one row per weekday, empty on days
with no observation, no forward or backward fill), at main `ea4f658`. Kept: FX from FRED H.10 and four central banks,
10-year yields (Tesouro Transparente, Banxico, SARB, BondSpot), BIS policy rates, CDI/TIIE/JIBAR, US 10-year, VIX,
fed funds; each column with its public source and licence basis in the manifest. Left out, with the reason in the
manifest's `excluded`:
- `FX_TR`, `FX_ID`, `FX_PL`, `DXY`: Yahoo Finance (terms do not license redistribution); the three FX series also pass
  through `clean_spikes`, which drops a tick using the **next** day's move (look-ahead). PLN is covered by NBP.
- `Y10_TR`: not point-in-time. `turkey_10y` screens prints against a **centred** 11-day median and drops linkers by
  each bond's **whole-sample** median, which includes 2020+ prints.
- `USD_BROAD`: revised vintage (FRED DTWEXBGS is recomputed when trade weights are revised).
- Known data issue kept as published: `STR_ZA` 2010-06-22 = 0.63 (one implausible source print).
- VIX: Cboe's copyright; FRED reprints it with permission. It is held only in the private store and never published.
  Remove it from the manifest if you prefer.

## 2. Builder and loader

- **Builder** (`python -m nightshift.explore_data build --authorised-by NAME --store-root <em-macro-data clone>`):
  opens only the manifest's files and columns. It refuses forward-looking or revised names (`next`, `fwd`, `lead`,
  `revis`, `vintage`, `latest`, ...), columns not marked `point_in_time: true`, columns without a source and licence,
  licensed sources (Norgate, Databento, settlements, em-macro-data), and paths outside the source root. It reads each
  file **as bytes**. The date must be the first column. The first ten bytes of each line are compared with main's
  cutoff before the line is decoded or split, and reading stops at the first later line. So no 2020+ row is ever
  decoded, tokenised, parsed or converted. The tests' post-cutoff rows are poison (invalid UTF-8, NUL bytes,
  unterminated quotes, words where numbers belong), and the tokeniser and converters are wrapped to fail on them.
  The build also records the source commit and blob and refuses a modified source. It refuses under a night lock;
  the night shift never builds.
- **Loader** (`from nightshift.explore_data import load; df = load(["FX_BR", "VIX"])`): reads main's cutoff fresh and
  main's manifest through `git show origin/main:` after a fresh fetch, never the checkout. It fetches the extract from
  the private store: `EM_MACRO_DATA`, then `../em-macro-data`, then a temporary blobless clone without checkout that
  downloads only that one file and is deleted, so no settlement or ledger file reaches disk. It serves the extract
  only if its sha256 is main's, and refuses a checkout copy of the manifest that differs from main's, any row after
  main's cutoff, and any series not in the manifest. Inside the sandbox it reads only the verified bundle: no git, no
  network.

## 3. The gate

`explore_data.explorer_gate()` must return no reasons before night-explorer may run. `guard check night-explorer`,
`guard next` and `state acquire night-explorer` apply it, and so does `explore_sandbox create`, which is protected
code, in case `guard.py` (unprotected) is edited on dev. The gate is evaluated whenever a caller does not pass it,
and it is closed if it cannot be evaluated. All of these must hold on **origin/main**:
1. main's `explorer.data_end` is readable, and the manifest is built and ends on or before it.
2. The four files in the table exist.
3. main's CODEOWNERS protected block covers all four. Lines outside the block do not count.
4. main's `.claude/routines/night-explorer.md` runs `python -m nightshift.explore_sandbox create`, i.e. you have
   applied section 5.

## 4. The sandbox

`python -m nightshift.explore_sandbox create --dest /tmp/explore-<stamp>` makes a **plain directory with no `.git`**.
It holds only an allowlist of dev's files: `CLAUDE.md`, `requirements.txt`, `.claude/agents/explorer.md`,
`nightshift/`, `lab/` and `docs/prereg_drafts/`. No path anywhere in it has a `data`, `results` or `fixtures`
component, and links and submodules are skipped. It also holds the bundle `.explore/`:
- `sandbox.json`: cutoff, hashes, commits and a file inventory;
- `manifest.json` and `extract.csv`, both verified against main;
- `tested_trials.csv`: trial id, name, hypothesis and design sample only, never results or decisions;
- `exploration_log.csv`: dev's variant log. Every row must end by the cutoff, or the sandbox is refused.
- `out/` for the explorer's outputs.

`create` refuses a destination inside any git work tree, and then audits its own tree. A worktree or sparse checkout
would not do this job: it keeps the object database, so `git show origin/main:data/...` would still print 2020+ rows.

`python -m nightshift.explore_sandbox collect --sandbox DIR` runs from the routine's checkout after the explorer
returns. It logs every variant from `.explore/out/variants.csv` again through `nightshift.logs`, against main's
cutoff fetched fresh. In the sandbox, `logs.py` checks against the sandbox's own copy of the cutoff, so those rows are
provisional. A refused row makes the exit 1. It copies back only new or changed files under `lab/sleeves/`,
`docs/prereg_drafts/` and `.explore/out/exploration/` (to `results/exploration/`), each at most 2 MB. Nothing else
leaves the sandbox.

## 5. Drafts for Ethan (protected files: not applied by this change)

**`.claude/routines/night-explorer.md`, section 2** (replaces "## 2. Explore"):

````markdown
## 2. Explore (in the sandbox only)
```bash
SBX=/tmp/explore-$(date -u +%Y%m%dT%H%M%S)
python -m nightshift.explore_sandbox create --dest "$SBX"   # exit 4: gate closed, 1: refused -> release blocked
```
If create does not exit 0, release with `--outcome blocked` and its message, and end. Otherwise call the Agent tool
with `subagent_type: explorer` (`model: sonnet` in safe mode). Its prompt says: "Your working directory is $SBX: `cd
$SBX` first and stay there. Read only files under $SBX. Data comes only from `from nightshift.explore_data import
load` (Python run from $SBX). Log every variant with `python -m nightshift.logs variant ...` run from $SBX. Write
tables under `$SBX/.explore/out/exploration/<hypothesis>/`, sleeves under `$SBX/lab/sleeves/` and drafts under
`$SBX/docs/prereg_drafts/`. Never use an absolute path outside $SBX or `..`. Never use git, curl, wget, pip, or any
other network command or library."
After it returns:
```bash
scripts/night_commit.sh "night-explorer: <hypothesis>" -- python -m nightshift.explore_sandbox collect --sandbox "$SBX"
rm -rf "$SBX"
```
If collect exits 1 (a refused variant or file), the run is `failed` and its refused lines go in the release note.
A run with no collected variant is `empty`.
````

**`.claude/agents/explorer.md`:**
- "Read first" becomes `CLAUDE.md`, `.explore/tested_trials.csv` (what has been tested: never repeat a trial, never
  touch T25-T26), `.explore/exploration_log.csv`, and `.explore/sandbox.json` (`explorer`, `cutoff`). Do not read
  `trials.csv` or `docs/prereg/`: they carry 2020-2026 results.
- Step 2 becomes: "Read data **only** through `from nightshift.explore_data import load`. It serves main's verified
  extract (26 public daily series to 2019-12-31; list in `.explore/manifest.json`). Never open other data, never
  fetch data from the web, never compute on anything `load` did not return. If it refuses, stop and report the
  refusal."
- Step 4 becomes: scratch code in the sandbox, and kept tables under `.explore/out/exploration/<hypothesis>/`.
- Consider dropping `WebSearch` from `tools:` (see residual 3).

## 6. What this does not close (residuals; why the explorer stays off until you decide)

1. **Network from Bash.** em-macro is a public repository, so `curl` to raw.githubusercontent.com, `pip download`,
   or `git clone` of it, and FRED and Yahoo, all serve 2020+ data. The sandbox cannot stop this. What can:
   - A separate cloud environment for the explorer with network policy **None**. Environments set it as None,
     Limited (allowlist) or Full, and scheduled tasks inherit it.
   - Claude Code's sandboxed Bash: `sandbox.enabled`, `sandbox.network.allowedDomains: []`,
     `sandbox.filesystem.denyRead` on the routine's checkout and the store. Its documentation covers local machines;
     whether these keys apply in cloud sessions is **not confirmed** and must be tested before relying on them.
   Note that `Read(...)` deny rules do not stop `cat` through Bash.
2. **The routine's own checkout by absolute path.** The explorer is a subagent in the same container, so
   `cat /home/user/em-macro/data/...` works unless Bash is sandboxed (as in 1) or the explorer runs in another session
   whose checkout is only the sandbox.
3. **WebSearch snippets** can quote 2020+ moves.
4. **The model's own training data** covers 2020-2025 markets. Hypotheses can be shaped by hindsight however the data
   is fenced. Only a confirmatory pre-registered test on 2020-2026 data (yours, never the night shift's) settles an
   idea.

Detection after the fact: `collect` re-checks every variant against main's cutoff, The Opposition reviews every
nominated idea, and the explorer's transcript can be searched for network or out-of-sandbox commands. A morning-report
check for that would be a queue item.

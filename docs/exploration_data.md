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
`guard next` and `state acquire night-explorer` apply it. The gate is evaluated whenever a caller does not pass it,
and it is closed if it cannot be evaluated. All of these must hold on **origin/main**:
1. main's `explorer.data_end` is readable, and the manifest is built and ends on or before it.
2. The four files in the table exist.
3. main's CODEOWNERS protected block covers all four. Lines outside the block do not count.
4. main's `.claude/routines/night-explorer.md` makes the sandbox with main's extracted code
   (`python -I "$MAINCODE/run.py" --repo "$PWD" create`), i.e. you have applied section 5.

`guard.py`, `state.py`, `config.py`, `protected.py` and `nightshift/__init__.py` are **not** protected, and Python runs
them, from whatever checkout it imports, before any protected module. A dev edit to `config.py` can loosen the
cutoff that dev's copy of `logs.py` or `explore_sandbox.py` sees (The Opposition's F1, proven by
`test_q019_F1_...`). So protecting the four files does not make dev's running copy trustworthy. The routine in
section 5 deals with this. It runs `create` and `collect` from **main's** `nightshift/`, fetched by URL and extracted
afresh for each step with `git archive`, outside every checkout, and run with `python -I`. `create` applies the gate
again there, and the sandbox's own `nightshift/` also comes from main. Gate check 4 requires those invocations.

That defends against **dev edits** (a night PR, an accident). It does **not** defend against an explorer acting
adversarially in the same container (section 6, residual 8). There, the only real boundary is a separate session
or environment.

## 4. The sandbox

`create` makes a **plain directory with no `.git`**. Only an allowlist of files goes in:
- From **main** (code and rules): `CLAUDE.md`, `requirements.txt`, `.claude/agents/explorer.md`, `nightshift/`,
  `lab/__init__.py`, `lab/book.py`, and the two folders' READMEs.
- From **dev** (the night's outputs so far): only `lab/sleeves/*.yaml` and `docs/prereg_drafts/*.md`, with no
  subfolders. Each passes the same screen as a collected file (below), and any that fails is skipped and listed.
- No path anywhere in it has a `data`, `results`, `fixtures` or `.explore` component. Links and submodules are
  skipped.

It also holds the bundle `.explore/`:
- `sandbox.json`: cutoff, hashes, commits and a file inventory.
- `manifest.json` and `extract.csv`, both verified against main.
- `tested_trials.csv`: trial id and name only. The hypothesis text can carry outcomes (e.g. "the failed T01").
- `exploration_log.csv`: dev's variant log without `params`, `code_ref` or `notes`. Every row must end by the cutoff,
  or the sandbox is refused, and a description with a post-cutoff date stamp is withheld.
- `out/` for the explorer's outputs.

`create` refuses a destination inside any git work tree, then audits its own tree. A worktree or sparse checkout
would not do this job: it keeps the object database, so `git show origin/main:data/...` would still print 2020+ rows.
Inside the sandbox the loader never reads the private store, and `build` and `pin` refuse.

`collect --sandbox DIR --into CHECKOUT` runs after the explorer returns. It logs every variant from
`.explore/out/variants.csv` again through `nightshift.logs`, against main's cutoff fetched fresh. Inside the sandbox
`logs.py` checks against the sandbox's own copy of the cutoff, so those rows are only provisional. A refused row makes
the exit 1.

It copies back only new or changed files, and each must pass a screen. The same screen applies to dev's files on
the way into the sandbox:
- `lab/sleeves/*.yaml`: at most 20 kB. A date stamp after the cutoff is allowed only in its own `launched:
  YYYY-MM-DD` and `retire_on: YYYY-MM-DD` lines, exactly that and once each.
- `docs/prereg_drafts/*.md`: at most 200 kB. An explicit test window (`2020-01..2026-09`) and a year range
  (`2020-2026`) are planning text and allowed; any other stamp after the cutoff is refused.
- Tables under `.explore/out/exploration/<hypothesis>/`, copied to `results/exploration/`: at most 2 MB. They must sit
  in a hypothesis folder, so a table can never replace `results/exploration/log.csv`.
- Every file must be UTF-8 text with no date stamp after the cutoff in any recognised form: ISO with `-`, `/`, `_` or
  `.`; compact (`20200302`); day-first (`02.03.2020`); month names (`Mar 2020`); and year ranges (`2020-26`). It must
  be free of the value of any credential-like environment variable. It is read with `O_NOFOLLOW`, and the real path
  of the open file must be inside the sandbox, so a link swapped in after the check cannot redirect the read.
- Variants: rows whose free text (id, description, metric, value, params, notes) carries such a stamp are refused,
  and in the sandbox's copy of the log they are withheld.

Nothing else leaves the sandbox. These screens are tripwires, not proofs: they catch dated rows and pasted secrets,
not prose such as "Sharpe 0.9 out of sample" (residual 7).

## 5. Drafts for Ethan (protected files: not applied by this change)

**`.claude/routines/night-explorer.md`, section 2** (replaces "## 2. Explore"):

````markdown
## 2. Explore (in the sandbox only, with main's code extracted afresh each time)
```bash
MAIN_URL=https://github.com/EthanC100/em-macro.git
fresh_main() {   # main's nightshift/, fetched by URL (not this checkout's origin), hooks off, into a new directory
  local d; d=$(mktemp -d /tmp/main-code-XXXXXX)
  git -c core.hooksPath=/dev/null fetch -q "$MAIN_URL" main &&
  git -c core.hooksPath=/dev/null archive FETCH_HEAD nightshift | tar -x -C "$d" &&
  printf '%s\n' 'import pathlib, sys; sys.path.insert(0, str(pathlib.Path(__file__).parent))' \
    'from nightshift.explore_sandbox import main; sys.exit(main(sys.argv[1:]))' > "$d/run.py" && echo "$d"
}
SBX=/tmp/explore-$(date -u +%Y%m%dT%H%M%S)
MAINCODE=$(fresh_main)
python -I "$MAINCODE/run.py" --repo "$PWD" create --dest "$SBX"   # exit 4: gate closed, 1: refused -> blocked
rm -rf "$MAINCODE"
```
If create does not exit 0, release with `--outcome blocked` and its message, and end. Otherwise call the Agent tool
with `subagent_type: explorer` (`model: sonnet` in safe mode). Its prompt says: "Your working directory is $SBX: `cd
$SBX` first and stay there. Read only files under $SBX. Data comes only from `from nightshift.explore_data import
load` (Python run from $SBX). Log every variant with `python -m nightshift.logs variant ...` run from $SBX. Write
tables under `$SBX/.explore/out/exploration/<hypothesis>/`, sleeves under `$SBX/lab/sleeves/` and drafts under
`$SBX/docs/prereg_drafts/`. Never use an absolute path outside $SBX or `..`. Never use git, curl, wget, pip, or any
other network command or library. Never start background processes."
After it returns, with main's code extracted **again** (the explorer could have edited the first copy), collect
first, outside `night_commit.sh` (unprotected, dev's), then commit:
```bash
MAINCODE=$(fresh_main)
python -I "$MAINCODE/run.py" --repo "$PWD" collect --sandbox "$SBX" --into "$PWD"; COLLECT=$?
rm -rf "$SBX" "$MAINCODE"
scripts/night_commit.sh "night-explorer: <hypothesis>" -- true
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
- Consider dropping `WebSearch` from `tools:` (see residual 4).

## 6. What this does not close (residuals; why the explorer stays off until you decide)

1. **Network from Bash.** em-macro is a public repository, so `curl` to raw.githubusercontent.com, `pip download`,
   or `git clone` of it, and FRED and Yahoo, all serve 2020+ data. The sandbox cannot stop this. What can:
   - A separate cloud environment for the explorer with network policy **None**. Environments set it as None,
     Limited (allowlist) or Full, and scheduled tasks inherit it.
   - Claude Code's sandboxed Bash: `sandbox.enabled`, `sandbox.network.allowedDomains: []`,
     `sandbox.filesystem.denyRead` on the routine's checkout and the store. Its documentation covers local machines;
     whether these keys apply in cloud sessions is **not confirmed** and must be tested before relying on them.
   Note that `Read(...)` deny rules do not stop `cat` through Bash.
2. **The routine's own checkout, and the private store, by absolute path or with the environment's credentials.**
   The explorer is a subagent in the same container. It inherits the routine's environment: the git proxy's
   credentials for every repository attached to the routine, and `DATA_REPO_READ_TOKEN` if that is set. So `cat
   /home/user/em-macro/data/...`, `git -C /home/user/em-macro show origin/main:results/...` and a clone of em-macro-data
   (licensed settlements) all work unless Bash is sandboxed (as in 1) or the explorer runs in another session that has
   only the sandbox. In code, the sandbox's own loader refuses to touch the store, but that only removes the
   convenient route. The night-explorer environment should not carry `DATA_REPO_READ_TOKEN`.
3. **Background processes.** A process the explorer starts with `nohup ... &` can outlive it and write into the
   checkout between `collect` and the commit. `night_commit.sh` commits only its listed paths, but
   `results/exploration` and `lab/sleeves` are among them.
4. **WebSearch snippets** can quote 2020+ moves.
5. **Self-declared windows.** A variant's `data_start`/`data_end` are what the explorer says. Inside an airtight
   sandbox that is enough, because only the extract exists; with residuals 1-3 open, a variant computed on 2020+ data
   can declare 2019. Free text (descriptions, drafts) is screened for date stamps only.
6. **Vintages.** The kept columns are the sources' current series (Banxico `LA-MAS-RECIENTE`, FRED's current
   vintage, BIS's own compilation), not archived as-of copies. Market prices and fixings are rarely revised; the
   manifest says so, and no column was checked against archived vintages.
7. **Free text and non-stamp numbers.** The screens catch date stamps in many forms (ISO, compact, day-first, month
   names, year ranges), but not prose like "Sharpe 0.9 out of sample", nor an undated column of numbers. They are
   tripwires.
8. **An adversarial explorer in the same container** (The Opposition's re-review, N1, N2 and N5). With Bash as the
   routine's user it can:
   - edit anything writable: an extracted main-code directory before it is used, the checkout's `.git` (hooks, a
     forged `origin`), site-packages `.pth` files (which `python -I` still runs), and `git`/`python` themselves;
   - make a `.git` in the sandbox, which switches off the sandbox loader's store refusals;
   - write its own clone code.
   Section 5's fresh extraction by URL, with hooks off, and `collect` outside `night_commit.sh` narrow this. They
   cannot close it. **Before the explorer is enabled, run it in its own session whose container holds only the
   sandbox, with network policy None** (residuals 1-3 and 8 then close together). Also consider protecting
   `scripts/night_commit.sh`, which every night routine runs from dev.
9. **The model's own training data** covers 2020-2025 markets. Hypotheses can be shaped by hindsight however the data
   is fenced. Only a confirmatory pre-registered test on 2020-2026 data (yours, never the night shift's) settles an
   idea.

Detection after the fact: `collect` re-checks every variant against main's cutoff, The Opposition reviews every
nominated idea, and the explorer's transcript can be searched for network or out-of-sandbox commands. A morning-report
check for that would be a queue item.

## 7. The Opposition's review (2026-11-12) and what changed

Asked to read 2020+ data as the explorer would. Verdict: advisory, no block, p_works 20.

| | finding | now |
|---|---|---|
| F1 | protected modules import dev's unprotected `config.py`, `protected.py`, `__init__.py`; a dev `config.py` can loosen the cutoff | against dev edits: closed by running `create`/`collect` from main's code extracted afresh (section 5; `--repo`, `--into`); proven by a test in which dev's code accepts a 2024 variant and main's refuses it. Open until the routine change is applied. Against the explorer itself: see N1 |
| F2 | whole folders from dev (`nightshift/`, `lab/`, `docs/prereg_drafts/`) can carry planted copies of 2020+ data or results | code from main; from dev only `lab/sleeves/*.yaml` and `docs/prereg_drafts/*.md`, screened (a tripwire, see N3) |
| F3 | `collect` follows a linked folder (store files to the public repo), can replace `results/exploration/log.csv`, can publish `env` output | closed for links (now also at read time, N6) and for `log.csv`; credential values refused (a tripwire, see N7) |
| F4 | the store and its credentials are reachable from the sandbox (`_blob_from_temp_clone`), and git tracing could log the token | partly: the sandbox loader refuses store access, git trace variables are dropped; the environment's credentials remain (residual 2) |
| F5 | `tested_trials.csv` hypothesis text carries outcomes | closed: id and name only |
| F6 | the copied log's free text and the self-declared `data_end` | log trimmed and screened; self-declaration remains (residual 5) |
| F7 | network, absolute paths, background writes | documented (residuals 1-3) |
| F8 | kept columns are current vintages, not as-of | documented in the manifest (`point_in_time_basis`) and residual 6 |
| builder | `build` run inside the sandbox against the checkout could launder a 2026 extract into the bundle | closed: `build` and `pin` refuse inside a sandbox (the absolute-path route remains, residual 2) |

**Re-review of the fixes** (same day; advisory, no block, p_works 20):

| | finding | now |
|---|---|---|
| N1 | the explorer can edit the extracted main code in /tmp before `collect` reuses it | the draft extracts afresh for `collect`; an adversarial explorer in the container remains (residual 8) |
| N2 | dev's `night_commit.sh` wraps `collect`; `.git` hooks or a forged `origin` in the checkout; `.pth` files under `python -I` | the draft runs `collect` outside `night_commit.sh`, fetches main by URL with `core.hooksPath=/dev/null`; `.pth` and the rest remain (residual 8); protect `night_commit.sh`: your call |
| N3 | whole sleeve lines starting `launched:` were exempt; drafts allowed month stamps; only ISO stamps were recognised | exempt only an exact `launched: YYYY-MM-DD` / `retire_on: YYYY-MM-DD`, once each; drafts allow only explicit windows (`2020-01..2026-09`) and year ranges; stamps recognised in ISO, `/`, `_`, `.`, compact, day-first and month-name forms and as year ranges. Still a tripwire (residual 7) |
| N4 | free text such as `sharpe_2020_26` in the variant log | variant free text is screened at `collect` (row refused) and in the sandbox's copy of the log (withheld); prose remains (residual 7) |
| N5 | `mkdir $SBX/.git` switches off the sandbox loader's store refusals | documented: those refusals remove a convenience, not a capability (residuals 2 and 8) |
| N6 | `collect` checked a path, then read it (a link swapped in between) | closed: read with `O_NOFOLLOW` and the real path of the open descriptor checked inside the sandbox |
| N7 | the credential screen misses encoded or split values | documented (tripwire) |
| N8 | the gate's routine check covered `create` only | it now requires the fresh extraction twice and both the `create` and `collect` invocations |


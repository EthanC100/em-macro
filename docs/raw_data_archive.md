# Raw data archive

**Rule (from 2026-11-04):** raw data used by any trial is kept, not only hashed. Each trial's raw files are packaged
as compressed archives and attached to the GitHub release **`raw-data-archive`** of this repository; their SHA-256
hashes are recorded below. `data/raw/` is gitignored, and sources revise their history, so a hash alone cannot
bring back the data a trial used.

**For a new trial:** before the trial's run is reported, run

```
python -m em_macro.archive_raw pack <trial id> data/raw/<trial's raw folder>   # archive + manifest -> dist/raw_archive/, row below
python -m em_macro.archive_raw upload dist/raw_archive/<asset> ...             # creates the release if needed (needs `gh`)
```

and commit the updated table. `pack` writes a deterministic `.tar.gz` (sorted members, fixed owner, modes and
timestamps) and a per-file manifest (path, bytes, SHA-256). An archive over 1.9 GB is split into `.part001`,
`.part002`, ... (GitHub's limit is 2 GiB per release asset); join with `cat <asset>.part* > <asset>`. `upload`
refuses a file whose SHA-256 differs from this record and never replaces an asset already on the release.
`python -m em_macro.archive_raw check <files>` checks downloaded assets against the record.

**Restore:** download the asset from the release, check it, and extract it into `data/raw/`:
`python -m em_macro.archive_raw check <asset> && tar -xzf <asset> -C data/raw`.

## Assets

| trial | asset | bytes | SHA-256 | contents | recorded | status |
|---|---|---|---|---|---|---|
| T02 | `econ_momentum_raw_2026-11-04.tar.gz` | 16533509 | `9be8876bba5596594a21e7ea7bd76b0dcb7a878018728c9b96a69e8081558f3c` | `data/raw/econ_momentum/` as used in the T02 run: 336 files (OECD revisions, ECB RTD, OECD KEI, ALFRED); from `trial/T02-econ-momentum` `0ba5ce4`, unchanged | 2026-11-04 | pending upload |

## Notes on what is and is not archived (2026-11-04)

- **Status `pending upload`.** The release `raw-data-archive` has not been created yet: the session that set this
  up could not create GitHub releases or upload assets (its GitHub access has no release-creation call, and tag
  pushes are refused by its git proxy, as for `v1.0-frozen`). To publish, from a normal clone with `gh` logged in:
  `git show origin/trial/T02-econ-momentum:data/kept/T02/econ_momentum_raw_2026-11-04.tar.gz > econ_momentum_raw_2026-11-04.tar.gz && python -m em_macro.archive_raw upload econ_momentum_raw_2026-11-04.tar.gz`,
  then commit this file (the status column changes to `on release`). Until then the archive is safe in git on
  `trial/T02-econ-momentum`.

- **T02 (economic momentum, ledger T13).** The raw set as used in the T02 run (`data/raw/econ_momentum/`, 336
  files: OECD revisions, ECB real-time database, OECD KEI, ALFRED vintages) was packaged by the T02 session as
  `econ_momentum_raw_2026-11-04.tar.gz` and committed on branch `trial/T02-econ-momentum` (commit `0ba5ce4`,
  `data/kept/T02/`). That archive is the asset above, byte for byte: its SHA-256 is the one T02 recorded in
  `results/T02/raw_data_verification.md`, so it was not repackaged (repackaging would change the hash). Checked on
  2026-11-04 against T02's manifests (`results/T02/raw_data_manifest.csv` with the 2026-11-04 addendum): all 329
  data files identical; the 7 ALFRED download pages differ and the 2 download logs are absent, as T02's
  verification already records ("no action": they hold no data). No split was needed (16.5 MB).
  To get the file: `git show origin/trial/T02-econ-momentum:data/kept/T02/econ_momentum_raw_2026-11-04.tar.gz > econ_momentum_raw_2026-11-04.tar.gz`.
- **Other trials of this repository** (`trials.csv`: T01/v1.0, T05, T06, T07, T09, T10, T11, T12/T01 trend
  sleeve). Their raw downloads were cached in `data/raw/` of session containers and GitHub Actions caches that no
  longer exist, so there is nothing left to archive. The raw files that are in git (`data/raw/bondspot/`,
  `data/raw/bist/`, `data/raw/imf_weo/`, `data/events/raw/`) are kept by git history at each trial's commit and
  are not duplicated here. v1.0's results do not depend on the lost files: `python -m em_macro.verify_v1`
  rebuilt them exactly from a fresh download on 2026-11-04.
- **Trials in other repositories** (ledger ids T02 gold events, T03, T04 and T08 in `trials.csv`) are out of scope
  here.

# Raw data archive

**Rule (from 2026-11-04):** raw data used by any trial is kept, not only hashed. Each trial's raw files are packaged
as a compressed archive whose SHA-256 is recorded below. An archive of **50 MB or less is committed to the
repository under `data/kept/<trial>/`** (the default); a larger one is attached to the GitHub release
**`raw-data-archive`** of this repository instead. `data/raw/` is gitignored, and sources revise their history, so
a hash alone cannot bring back the data a trial used.

**For a new trial:** before the trial's run is reported, run

```
python -m em_macro.archive_raw pack <trial id> data/raw/<trial's raw folder>   # archive + manifest; <= 50 MB -> data/kept/<trial>/, row below
git add data/kept/<trial id> docs/raw_data_archive.md                          # and commit
python -m em_macro.archive_raw upload dist/raw_archive/<asset> ...             # only for an archive over 50 MB (needs `gh`)
```

`pack` writes a deterministic `.tar.gz` (sorted members, fixed owner, modes and timestamps) and a per-file manifest
(path, bytes, SHA-256). When the archive is 50 MB or less, `pack` moves both into `data/kept/<trial>/` and records
them with status `kept in repository`; commit that folder with the updated table. A larger archive stays in
`dist/raw_archive/` with status `pending upload` until `upload` attaches it to the release (`pack --release` forces
this for any size). An archive over 1.9 GB is split into `.part001`, `.part002`, ... (GitHub's limit is 2 GiB per
release asset); join with `cat <asset>.part* > <asset>`. `upload` refuses a file whose SHA-256 differs from this
record and never replaces an asset already on the release. `python -m em_macro.archive_raw check <files>` checks
any archive, kept or downloaded, against the record.

**Restore:** take the archive from `data/kept/<trial>/` (or download it from the release), check it, and extract it
into `data/raw/`: `python -m em_macro.archive_raw check <asset> && tar -xzf <asset> -C data/raw`.

## Assets

| trial | asset | bytes | SHA-256 | contents | recorded | status |
|---|---|---|---|---|---|---|
| T02 | `econ_momentum_raw_2026-11-04.tar.gz` | 16533509 | `9be8876bba5596594a21e7ea7bd76b0dcb7a878018728c9b96a69e8081558f3c` | `data/raw/econ_momentum/` as used in the T02 run: 336 files (OECD revisions, ECB RTD, OECD KEI, ALFRED); `data/kept/T02/` (commit `0ba5ce4`), unchanged | 2026-11-04 | kept in repository (`data/kept/T02/econ_momentum_raw_2026-11-04.tar.gz`) |

## Notes on what is and is not archived (2026-11-04)

- **Status `kept in repository`.** The T02 archive is committed on `main` as
  `data/kept/T02/econ_momentum_raw_2026-11-04.tar.gz` (16.5 MB, under the 50 MB limit), which satisfies the
  retention rule; no GitHub release is needed for it. The release `raw-data-archive` does not exist yet and is
  created by `upload` only when a trial's archive is over 50 MB.
- **T02 (economic momentum, ledger T13).** The raw set as used in the T02 run (`data/raw/econ_momentum/`, 336
  files: OECD revisions, ECB real-time database, OECD KEI, ALFRED vintages) was packaged by the T02 session as
  `econ_momentum_raw_2026-11-04.tar.gz` and committed on branch `trial/T02-econ-momentum` (commit `0ba5ce4`), now
  on `main` (PR #6) as `data/kept/T02/econ_momentum_raw_2026-11-04.tar.gz`. That archive is the asset above, byte for byte: its SHA-256 is the one T02 recorded in
  `results/T02/raw_data_verification.md`, so it was not repackaged (repackaging would change the hash). Checked on
  2026-11-04 against T02's manifests (`results/T02/raw_data_manifest.csv` with the 2026-11-04 addendum): all 329
  data files identical; the 7 ALFRED download pages differ and the 2 download logs are absent, as T02's
  verification already records ("no action": they hold no data). No split was needed (16.5 MB).
- **Other trials of this repository** (`trials.csv`: T01/v1.0, T05, T06, T07, T09, T10, T11, T12/T01 trend
  sleeve). Their raw downloads were cached in `data/raw/` of session containers and GitHub Actions caches that no
  longer exist, so there is nothing left to archive. The raw files that are in git (`data/raw/bondspot/`,
  `data/raw/bist/`, `data/raw/imf_weo/`, `data/events/raw/`) are kept by git history at each trial's commit and
  are not duplicated here. v1.0's results do not depend on the lost files: `python -m em_macro.verify_v1`
  rebuilt them exactly from a fresh download on 2026-11-04.
- **Trials in other repositories** (ledger ids T02 gold events, T03, T04 and T08 in `trials.csv`) are out of scope
  here.

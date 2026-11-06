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
| T16-T19 | `T16-T19_raw_raw_2026-11-04.tar.gz` | 1036968 | `7a1f4ae84b72d2d0715ae2d22ac100d8087537a277f20faa41dd6ede4d6c4079` | the cached raw downloads v1.0's build_inputs and the T16-T19 batch read on 2026-11-04 (members under raw/: bis, chile, colombia, fred, yahoo; extract into data/); the git-kept folders bist, bondspot and imf_weo are not duplicated | 2026-11-04 | kept in repository (`data/kept/T16-T19/T16-T19_raw_raw_2026-11-04.tar.gz`) |
| T16-T19 | `T16-T19_raw_raw_2026-11-04_manifest.csv` | 4913 | `879ba1ae0e634503a4c786c7a7eec17880186bede0b919acabbad5038c9a65d7` | per-file SHA-256 of T16-T19_raw_raw_2026-11-04.tar.gz | 2026-11-04 | kept in repository (`data/kept/T16-T19/T16-T19_raw_raw_2026-11-04_manifest.csv`) |
| T20-T22 | Norgate `2026-11_futures/manifest.csv` | 1326695 | `1d6657e637d337a6f26f79f8b20ba86490affbe33dd9f171c44e3cec9c0e5f60` | per-file SHA-256 of the 9,473 commodity contract files (licensed; private repo `EthanC100/em-macro-data`, commit `12d7a0b`) | 2026-11-06 | kept privately (decision 13: vendor licence forbids redistribution) |
| T20-T22 | Norgate `2026-11_financials/manifest.csv` | 126517 | `91d1d9e2411aceb31681086b96953faeac0e4c15b7fb7c42c404467e19aa5129` | per-file SHA-256 of the 886 financial-futures contract files (private, commit `bd24f9d`) | 2026-11-06 | kept privately |
| T20-T22 | Norgate `2026-11_metadata/metadata.csv` | 1111384 | `2efd5eaaeaa7401994a9cfbb740d1a31787f017e46a24ec1d26616aecd9cad9d` | per-contract first notice, quoted dates, point value and tick for 10,359 contracts (private, commit `bd24f9d`) | 2026-11-06 | kept privately |
| T23-T24 | AQR `Commodities-for-the-Long-Run-Index-Level-Data-Monthly.xlsx` | 454950 | `eeb89c65fa7dca2bfbbebb7af2cbecade7b470d6a4da52883e9413a162b5fe75` | public AQR data set (D3 benchmark: equal-weight excess return), downloaded 2026-11-06 from aqr.com; copy in the private repo `EthanC100/em-macro-data` under `norgate/derived/T23-T24/aqr/` | 2026-11-06 | kept privately (as Build 0's AQR files) |
| T23-T24 | AQR `Century-of-Factor-Premia-Monthly.xlsx` | 1784414 | `0bf8ba978e64964282ead98a6a25691218d4517d07c98c89e2716706f6f0a127` | public AQR data set, read by Build 0's `load_aqr` alongside the first (not used by any T23-T24 statistic); same location | 2026-11-06 | kept privately |
| T23-T24 | Norgate snapshots `2026-11_futures`, `2026-11_financials`, `2026-11_metadata` | — | as the T20-T22 rows above (re-checked 2026-11-06) | the same licensed inputs as T20-T22; nothing new exported | 2026-11-06 | kept privately |

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
- **T16–T19 (risk batch, ledger T16–T19).** The cached raw downloads that v1.0's `build_inputs` and the batch read on
  2026-11-04 (FRED, Yahoo, BIS policy rates and CPI, BanRep TRM, BCCh dollar via mindicador.cl; 51 files) were packed
  from a staging copy named `raw/` as `T16-T19_raw_raw_2026-11-04.tar.gz` (1.0 MB, kept in
  `data/kept/T16-T19/`). Members sit under `raw/`, so restore with `tar -xzf <asset> -C data/` (not `data/raw/`).
  The git-kept folders `bist`, `bondspot` and `imf_weo` are not duplicated. The processed input snapshots the batch
  used are those of commit `7886867` (`results/T16-T19/RUN.json`).
- **Other trials of this repository** (`trials.csv`: T01/v1.0, T05, T06, T07, T09, T10, T11, T12/T01 trend
  sleeve). Their raw downloads were cached in `data/raw/` of session containers and GitHub Actions caches that no
  longer exist, so there is nothing left to archive. The raw files that are in git (`data/raw/bondspot/`,
  `data/raw/bist/`, `data/raw/imf_weo/`, `data/events/raw/`) are kept by git history at each trial's commit and
  are not duplicated here. v1.0's results do not depend on the lost files: `python -m em_macro.verify_v1`
  rebuilt them exactly from a fresh download on 2026-11-04.
- **Trials in other repositories** (ledger ids T02 gold events, T03, T04 and T08 in `trials.csv`) are out of scope
  here.

## T20-T22 (commodity trials, 2026-11-06)

- **Norgate inputs.** These are licensed for personal use and cannot be redistributed, so they are not committed
  here (pre-registration decision 13). The exported contract files and their manifests are in the private repo
  `EthanC100/em-macro-data` under `norgate/`, and the manifests' SHA-256 hashes are in the table above.
- **Databento settlements.** Used for the Build 0 A5 cross-check, together with the per-request cost ledger. They
  are kept privately under `norgate/derived/build0/databento/`.
- **Other inputs.** The v1.1 baseline and the EUR/GBP conversion read v1.0's input snapshots at `7886867` and the
  T16-T19 raw cache in `data/kept/T16-T19/`, which was restored and checked before the run. No new public download
  was used.

## T23-T24 (T21 and T22 on 1979-1999, 2026-11-06)

- **Norgate inputs.** The same private snapshots as T20-T22, with the manifest hashes above; their SHA-256 were
  re-checked before the run (`results/T23-T24/RUN.json`).
- **AQR benchmark files.** Public, downloaded for check D3 (A3 on the window); kept privately with Build 0's practice,
  hashes above.
- **Per-market outputs** (held weights, signals, trades, daily gross by market, the A3 window series and the A9 window
  issues) are private, under `norgate/derived/T23-T24/` in `EthanC100/em-macro-data`.

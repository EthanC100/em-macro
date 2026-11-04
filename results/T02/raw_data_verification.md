# T02 step 1: re-download and verification of the raw macro vintages

Re-downloaded on 2026-11-04 with `python -m em_macro.t02_data download` into an empty `data/raw/econ_momentum/`.
Then checked with `python -m em_macro.t02_verify` against `results/T02/raw_data_manifest.csv` (written at the
data-feasibility step on 2026-11-03). Per-file results are in `results/T02/raw_data_verification.csv`.
**Nothing was computed from the data:** no signal, no return, no backtest.

| status | files |
|---|---|
| identical (same size and SHA-256) | 324 |
| hash differs | 12 |
| missing | 2 |

**Identical:** all 43 OECD revisions-database files (every edition of every series), all 7 ECB Real Time
Database files, and all 277 ALFRED vintage CSVs. The vintage counts per ALFRED series are unchanged (54, 37,
12, 67, 23, 50, 34), and no file is extra.

**Hash differs:**

| files | role in T02 | finding |
|---|---|---|
| `oecd_kei_latest/KEI_M_{CP,PRVM,TOVM,UNEMP,PP}_latest.csv` (5) | revised fallback series (pre-registration §2.4); PP is not used | Each file has the same size in bytes as on 2026-11-03. Its 56 series have the same first and last observation and the same number of observations (`coverage_oecd_kei` matches `data_coverage_oecd_kei_latest.csv` row for row). Two fresh downloads today are byte-identical to each other and to the file on disk, so today's response is deterministic; it differs from yesterday's. PP has had no new data since 2022-12 and also changed. That points to a change on the OECD side in row order or in an equal-length field, not to new data. **This cannot be confirmed:** the 2026-11-03 files were gitignored and are not available, and the manifest holds only their hashes. Whether any fallback value differs cannot be checked. |
| `alfred/<series>_downloadpage.html` (7) | HTML page from which the vintage dates are read | Each is 7 bytes shorter than on 2026-11-03. Two fresh downloads today are identical. The vintage lists on the pages give the same counts, and every vintage CSV they point to is identical, so the change is in page markup and not in any data used. |

**Missing:** `oecd_stes_revisions/_download_log.txt` and `oecd_kei_latest/_download_log.txt`. These are
console logs from the data step. `em_macro.t02_data download` does not write them, so a re-download cannot
recreate them. They hold no data.

## Addendum, 2026-11-04: decision and new hashes

**Decision (2026-11-04, before any computation):** proceed with the files downloaded on 2026-11-04. Nothing had
been computed when the difference was found, so the change cannot bias the result. Every first-release vintage
file (OECD revisions database, ECB RTD, ALFRED) reproduces the 2026-11-03 manifest exactly.

**The five OECD KEI files (revised fallback series).** Their new hashes are in
`results/T02/raw_data_manifest_addendum_2026-11-04.csv`, next to the 2026-11-03 hashes. The T02 run uses these
2026-11-04 files.

| file | bytes | SHA-256 (2026-11-04) |
|---|---|---|
| `oecd_kei_latest/KEI_M_CP_latest.csv` | 1,118,453 | `42b31c9cd1c33ef3353132c75859c838867bdc525c12b9e67332d38711f5bfe6` |
| `oecd_kei_latest/KEI_M_PP_latest.csv` | 439,717 | `42a9041875ed06314f39140be389357cadd5a6ad085bed1e0481c53062c68499` |
| `oecd_kei_latest/KEI_M_PRVM_latest.csv` | 2,815,749 | `ef3fecf917e4186bda6a8b6c84fd3cb080a1613e820e1b37c3078b872c991ecd` |
| `oecd_kei_latest/KEI_M_TOVM_latest.csv` | 769,140 | `2245a57825ba5c4a113553d66cf1f0b842b6955f99fec70ebbb888877e933bda` |
| `oecd_kei_latest/KEI_M_UNEMP_latest.csv` | 221,506 | `3a6af1d7e6273dbdd357f19c82a42a9e3c88f4e75b7eb9e15b7e8c0ff7da6787` |

The fallback values **cannot be shown equal** to those of the 2026-11-03 download, because those files were
not kept; only their hashes were recorded.

**ALFRED download pages (7) and console logs (2):** no action. The pages only list vintage dates, and every
vintage file they list is identical. The logs hold no data and are not written by the download code.

**Rule from now on:** raw files used in a trial are kept, not only their hashes. For T02, the complete raw set
as used in the run (336 files: OECD revisions, ECB RTD, OECD KEI, ALFRED) is kept in the repository as
`data/kept/T02/econ_momentum_raw_2026-11-04.tar.gz` (16.5 MB; SHA-256
`9be8876bba5596594a21e7ea7bd76b0dcb7a878018728c9b96a69e8081558f3c`). Restore it with
`tar -xzf data/kept/T02/econ_momentum_raw_2026-11-04.tar.gz -C data/raw`.

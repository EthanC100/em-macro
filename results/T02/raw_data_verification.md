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

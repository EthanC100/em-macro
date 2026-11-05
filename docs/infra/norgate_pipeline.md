# Norgate futures data pipeline (trial, November 2026)

Set up and first run on 2026-11-05 on the `horizons-norgate` Windows server
(`i-091fbf95cc5a6162a`, ap-southeast-2; see [aws_norgate_server.md](aws_norgate_server.md)).
Everything was done through SSM Run Command, except signing in to NDU (one RDP session; see below).
**No secrets are in this repo.** The vendor data is **not** in this repo either: it is only in the
private repo `EthanC100/em-macro-data`.

## Summary

| Item | Value |
|---|---|
| Subscription | Norgate trial, Futures Silver, 2 years of history (data starts **2024-11-05**) |
| Software | Norgate Data Updater (NDU) 4.2.2.65, `norgatedata` 1.0.77 (with pandas 3.1.1 and numpy 2.5.4) in Python 3.12.10 |
| Export script | [`scripts/norgate_export.py`](../../scripts/norgate_export.py) (`coverage`, `export`, `all`) |
| As-of date | 2026-11-05 (date of the last Futures database update); last daily bar is **2026-11-04** |
| Result | All 24 target markets **OK**: they have expired contracts, and a contract at least 12 months out with a current settlement |
| Output | 1,266 contract CSVs + `coverage.csv` + `all_markets.csv` + `manifest.csv` + `manifest.json` = 1,270 files, **18,826,054 bytes** (18.0 MiB) |
| Destination | `EthanC100/em-macro-data` (private; only collaborator EthanC100), branch `main`, folder `norgate/trial_2026-11/`, commit `ab2b862` |
| Integrity | All 1,268 manifest SHA-256 hashes checked against a fresh clone of the pushed repo: 0 mismatches |

## Setup

### Secrets

These are stored as SSM Parameter Store **SecureString** parameters in ap-southeast-2, encrypted with
the default `aws/ssm` key:

| Parameter | Contents |
|---|---|
| `/horizons/norgate/username` | Norgate trial username |
| `/horizons/norgate/password` | Norgate trial password |
| `/horizons/github/em-macro-data-token` | GitHub token with push access to `EthanC100/em-macro-data` |

The instance role (`AmazonSSMManagedInstanceCore` only) can read and decrypt them. The server reads
them with AWS CLI v2 into a variable and never prints them. Git gets the token through a temporary
`GIT_ASKPASS` helper that reads an environment variable, with `credential.helper` disabled, so it
is never written to disk, a command line or the remote URL.

To rotate a secret, run `aws ssm put-parameter --region ap-southeast-2 --type SecureString --overwrite --name <name> --value ...`
from a machine that holds the new value.

### NDU installation: what works and what doesn't

- **Download:** `https://norgatedata.com/downloads/ndu.4.2.2.65.setup.exe` (39,337,808 bytes,
  SHA-256 `1175491ee711152f9bb39f12a70a8f0661a1e44ff81cc41949054dc9d83aac7d`, Authenticode-signed
  by NorgateData Pty Ltd). It is an NSIS installer.
- **`/S` (silent) does not work on a fresh machine.** The installer hangs on a hidden prompt:
  ".NET version 4.7.2 is required … install it now?". This happens even though .NET 4.8 (release
  528449) is installed. Its start-up step reads optional registry values left by a previous
  install, and on a new machine that read fails. The failure leaves the installer's error flag set,
  and the .NET check misreads it as a missing .NET. When reinstalling, kill the hung process and
  run the normal wizard instead.
- **Wizard over SSM:** started without `/S` from SSM it runs (hidden) in session 0. Its buttons can
  be pressed by sending `WM_COMMAND`/`BM_CLICK` window messages from PowerShell. Steps: Next,
  accept the licence, Next (application folder default), Next (database folder default
  `C:\ProgramData\Norgate Data`), choose Update Automatically, Next, Install, untick "Run", Finish.
  It also installs the VC++ 2022 runtimes.
- Because the installer ran as SYSTEM, NDU's per-user settings (`HKCU\Software\NDU`) were written to
  SYSTEM's registry hive. They were copied to the Administrator profile, and a desktop shortcut
  was added.
- **NDU cannot run headless.** Started from SSM (SYSTEM, session 0) it crashes immediately: .NET
  `InvalidOperationException` in `Form.ShowDialog` (DevExpress splash screen). It needs an
  interactive desktop session.

### The one manual step: sign-in over RDP

NDU was started and signed in by a person over RDP as **Administrator**, and the first database
download ran there. The session was then **disconnected, not signed out**, so NDU keeps running.
`norgatedata` reaches NDU over its local API on `localhost:38889`, and this works from SSM (SYSTEM,
session 0) while NDU runs in the disconnected session 2.

**After every stop/start of the instance, NDU is not running** until someone RDPs in, starts it
from the desktop shortcut and disconnects. NDU keeps its sign-in, so this is a 1-minute step. To
remove it, the server would need an account that logs in automatically and starts NDU (a
security trade-off; it was not set up).

### Python

```powershell
& 'C:\Program Files\Python312\python.exe' -m pip install --upgrade norgatedata
```

The script is copied to `C:\horizons-norgate\norgate_export.py`. Output goes to
`C:\norgate-export\trial_2026-11\`.

## Markets available

Norgate offers **124 futures market sessions** in this trial (FX, equity indices, rates, bonds,
energy, metals, grains, softs, livestock, crypto). The full list, with exchange and contract count,
is `all_markets.csv` in the data repo. Of the 24 target markets, 22 use our code as the Norgate
symbol. The other two map as follows: **Brent `B` → `BRN`** (ICE Europe) and **Gasoil `G` → `GAS`**
(ICE Europe Low Sulphur Gasoil). The script tries only alternative spellings of the same contract
and never substitutes a different market.

| Market | Norgate | Exchange | Contracts (expired / live) | Delivery months | Contract range | Furthest live (months out) | 12-month check contract | Files (bytes) |
|---|---|---|---|---|---|---|---|---|
| CL | CL | NYMEX | 147 (24 / 123) | all 12 | CL-2024Z … CL-2037G | CL-2037G (123) | CL-2027X | 2,687,427 |
| B | BRN | ICE Europe | 171 (24 / 147) | all 12 | BRN-2025F … BRN-2039H | BRN-2039H (148) | BRN-2027X | 2,146,100 |
| HO | HO | NYMEX | 62 (24 / 38) | all 12 | HO-2024Z … HO-2030F | HO-2030F (38) | HO-2027X | 1,014,180 |
| RB | RB | NYMEX | 62 (24 / 38) | all 12 | RB-2024Z … RB-2030F | RB-2030F (38) | RB-2027X | 1,009,948 |
| NG | NG | NYMEX | 154 (24 / 130) | all 12 | NG-2024Z … NG-2037U | NG-2037U (130) | NG-2027X | 2,519,667 |
| G | GAS | ICE Europe | 98 (24 / 74) | all 12 | GAS-2024X … GAS-2032Z | GAS-2032Z (73) | GAS-2027X | 1,720,831 |
| HG | HG | NYMEX (COMEX) | 72 (24 / 48) | all 12 | HG-2024X … HG-2031Z | HG-2031Z (61) | HG-2027X | 939,943 |
| GC | GC | NYMEX (COMEX) | 57 (24 / 33) | all 12 | GC-2024X … GC-2032M | GC-2032M (67) | GC-2027X | 729,347 |
| SI | SI | NYMEX (COMEX) | 55 (24 / 31) | all 12 | SI-2024X … SI-2031N | SI-2031N (56) | SI-2027X | 666,045 |
| PL | PL | NYMEX | 38 (24 / 14) | all 12 | PL-2024X … PL-2029V | PL-2029V (35) | PL-2028F | 316,005 |
| PA | PA | NYMEX | 20 (8 / 12) | H M U Z | PA-2024Z … PA-2029U | PA-2029U (34) | PA-2027Z | 261,455 |
| ZC | ZC | CBOT | 23 (10 / 13) | H K N U Z | ZC-2024Z … ZC-2029Z | ZC-2029Z (37) | ZC-2027Z | 338,561 |
| ZS | ZS | CBOT | 31 (14 / 17) | F H K N Q U X | ZS-2024X … ZS-2029X | ZS-2029X (36) | ZS-2027X | 485,629 |
| ZW | ZW | CBOT | 24 (10 / 14) | H K N U Z | ZW-2024Z … ZW-2029N | ZW-2029N (32) | ZW-2027Z | 290,340 |
| KE | KE | KCBT | 24 (10 / 14) | H K N U Z | KE-2024Z … KE-2029N | KE-2029N (32) | KE-2027Z | 286,020 |
| ZM | ZM | CBOT | 36 (16 / 20) | F H K N Q U V Z | ZM-2024Z … ZM-2029Z | ZM-2029Z (37) | ZM-2027Z | 504,424 |
| ZL | ZL | CBOT | 36 (16 / 20) | F H K N Q U V Z | ZL-2024Z … ZL-2029Z | ZL-2029Z (37) | ZL-2027Z | 507,312 |
| SB | SB | ICE US | 20 (8 / 12) | H K N V | SB-2025H … SB-2029V | SB-2029V (35) | SB-2028H | 269,699 |
| KC | KC | ICE US | 17 (10 / 7) | H K N U Z | KC-2024Z … KC-2028H | KC-2028H (16) | KC-2027Z | 272,798 |
| CC | CC | ICE US | 20 (10 / 10) | H K N U Z | CC-2024Z … CC-2028U | CC-2028U (22) | CC-2027Z | 201,931 |
| CT | CT | ICE US | 25 (10 / 15) | H K N V Z | CT-2024Z … CT-2029V | CT-2029V (35) | CT-2027Z | 314,181 |
| LE | LE | CME | 22 (12 / 10) | G J M Q V Z | LE-2024Z … LE-2028M | LE-2028M (19) | LE-2027Z | 246,480 |
| GF | GF | CME | 25 (16 / 9) | F H J K Q U V X | GF-2024X … GF-2027X | GF-2027X (12) | GF-2027X | 216,559 |
| HE | HE | CME | 27 (16 / 11) | G J K M N Q V Z | HE-2024Z … HE-2028J | HE-2028J (17) | HE-2027Z | 270,433 |
| **Total** | | | **1,266 (406 / 860†)** | | | | | **18,215,315** |

The exchange is as Norgate reports it; COMEX metals appear as NYMEX. † Live means expiry date after
the as-of date (2026-11-05, the date of NDU's last database update in Singapore time). 843
contracts have a bar dated 2026-11-04, the latest trading day.

Each "12-month check contract" is the nearest live contract at least 12 months after the as-of
month. Each has a settlement on 2026-11-04, so the deferred curve beyond 12 months is quoted, not
just listed. File sizes are the contract CSVs only. The other files are `coverage.csv` 3,065,
`all_markets.csv` 5,837, `manifest.csv` 177,159 and `manifest.json` 424,678 bytes.

## Gaps and caveats

1. **History is limited to 2 years by the trial.** Every contract starts on or after 2024-11-05.
   751 contracts were already trading on that date, so their history is cut there. Expired
   contracts cover only expiries from Nov/Dec 2024 to Oct/Nov 2026, between 8 (PA, SB) and 24
   (monthly energy and metals) per market. A paid subscription would be needed for deeper history.
2. **Open interest lags one day.** On the latest bar (2026-11-04), `open_interest` is 0 for all 843
   contracts quoted that day. Of those, 310 also show 0 on 2026-11-03; these are mostly illiquid
   deferred contracts with genuinely zero OI. Treat OI on the last bar as not yet published. It
   should fill in when NDU next updates, so rerun the export to pick it up.
3. **Many rows are settlement only.** 224,653 of 418,671 rows (54%) have open = high = low = close
   and zero volume. These are settlement prices for contracts that did not trade that day, mostly
   far-deferred months. 319 contracts never traded at all in the window (e.g. CL-2031G onward):
   their files are settlement-only curves.
4. **Some days are missing.** A few contracts have no row on days when the rest of their market
   traded: NG 2036 contracts (10 contracts, 742 contract-days in total, starting March 2026), KE-2028U
   (36 days from 2026-05-19) and 9 CL 2036 contracts (2 days, 2025-11-18/19, right after listing).
   The export uses no padding, so these are genuine absences in Norgate's data; nothing has been
   filled in. All other target markets have no missing days.
5. **Prices are unadjusted and in exchange units.** For example, grains are in cents per bushel
   (ZC 436.5). Close is the settlement price.
6. **Line endings:** the CSVs use CRLF line endings, as written by Python's csv module on Windows.
   The data repo's `.gitattributes` has `norgate/** -text` so git never converts them, which would
   break the SHA-256 hashes.

## Rerunning

1. Start the instance, RDP in, start NDU from the desktop shortcut, wait for the update to finish
   (status bar), then disconnect (don't sign out).
   ```bash
   scripts/aws_server.sh start
   ```
2. Check that NDU is reachable over SSM. Expect `True`:
   ```powershell
   & 'C:\Program Files\Python312\python.exe' -c "import norgatedata as nd; print(nd.status(), nd.last_database_update_time('Futures'))"
   ```
3. Copy the current `scripts/norgate_export.py` to `C:\horizons-norgate\` (the first run sent it
   base64-encoded inside the SSM command), then run it:
   ```powershell
   $out = 'C:\norgate-export\trial_2026-11'      # use a new folder name for a new snapshot
   Remove-Item -Recurse -Force $out -ErrorAction SilentlyContinue
   & 'C:\Program Files\Python312\python.exe' -I C:\horizons-norgate\norgate_export.py all --out $out
   ```
   `coverage` alone takes about 12 seconds; `all` takes about 45 seconds for the 24 markets.
   `--markets CL GC` limits a run to some markets.
4. Push to the data repo from the server. The token comes from Parameter Store and is never printed:
   ```powershell
   $git = 'C:\Program Files\Git\cmd\git.exe'
   $env:GIT_TOKEN = & 'C:\Program Files\Amazon\AWSCLIV2\aws.exe' ssm get-parameter --region ap-southeast-2 `
       --name /horizons/github/em-macro-data-token --with-decryption --query Parameter.Value --output text
   '@echo off', 'echo %GIT_TOKEN%' | Set-Content C:\horizons-norgate\askpass.cmd -Encoding ascii
   $env:GIT_ASKPASS = 'C:\horizons-norgate\askpass.cmd'; $env:GIT_TERMINAL_PROMPT = '0'
   $repo = 'C:\horizons-norgate\em-macro-data'      # existing clone; re-clone from
                                                    # https://x-access-token@github.com/EthanC100/em-macro-data.git if missing
   & $git -C $repo -c credential.helper= pull --quiet origin main
   robocopy $out "$repo\norgate\trial_2026-11" /MIR /NFL /NDL /NJH /NJS /NP   # or a new folder for a new snapshot
   & $git -C $repo add -A; & $git -C $repo commit -m "Update Norgate trial export"
   & $git -C $repo -c credential.helper= push --quiet origin main
   Remove-Item C:\horizons-norgate\askpass.cmd; Remove-Item Env:GIT_TOKEN
   ```
   Then check the manifest hashes against a fresh clone. Note that `/MIR` also deletes files that
   are no longer exported.
5. Stop the instance: `scripts/aws_server.sh stop`.

## Script fixes made against the real API (2026-11-05)

- `last_quoted_date()` returns the **scheduled expiry date** for a live contract (e.g. CL-2037G →
  2037-01-20), not the date of its last bar. The original logic took the latest of those dates as
  "today", so it reported only one live contract per market and failed every 12-month check. Live
  now means expiry after the as-of date (taken from `last_database_update_time('Futures')`).
  The 12-month check also requires that contract to have a bar within 7 days of as-of.
- `exchange_name()` accepts only a security (contract) symbol, so it is now called with the
  market's first contract instead of the market-session symbol.
- Prices come back as float32. They are now written as the shortest text that round-trips (`50.54`,
  not `50.540000915527344`), and columns are read as arrays so `iterrows()` cannot upcast them.
- `coverage.csv` gained `as_of`, `last_expired_contract`, `furthest_live_contract` and the
  `deferred_12m_contract` and `deferred_12m_last_bar` fields; `all_markets.csv` gained `contracts`.

## Licence obligations (NDU End User Licence Agreement 20261002)

Accepting the EULA was part of the installation. It applies to everything in `em-macro-data/norgate/`:

- **Personal Use only.** No commercial or professional use, and no use on behalf of another person
  or organisation.
- Exports may be stored in private cloud and git hosting, but **no one else may have access**, so
  do not add collaborators to `em-macro-data` or make it public.
- **When the subscription ends, all exported data must be deleted**, including copies and backups.
  For git this means removing it from the history (or deleting the repo), not just from `main`.
- The software may not be reverse engineered or decompiled.

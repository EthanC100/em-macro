# Norgate futures data pipeline

This pipeline exports daily data for individual futures contracts, both live and expired, from
Norgate Data on the `horizons-norgate` Windows server (`i-091fbf95cc5a6162a`, ap-southeast-2; see
[aws_norgate_server.md](aws_norgate_server.md)). Everything runs through SSM Run Command, except
starting NDU, which needs one short RDP session (see below).

**This repo holds no secrets and no vendor data.** Exports, manifests and the detailed per-contract
coverage tables (`COVERAGE.md`) are kept only in the private repo `EthanC100/em-macro-data`, under
`norgate/<snapshot>/`.

## Components

| Item | Value |
|---|---|
| Subscription | Norgate Futures, 6 months, purchased November 2026. The earlier trial export was deleted |
| Software | Norgate Data Updater (NDU) 4.2.2.65, `norgatedata` (PyPI) in Python 3.12 |
| Export script | [`scripts/norgate_export.py`](../../scripts/norgate_export.py) (`coverage`, `export`, `all`) |
| Server paths | script `C:\horizons-norgate\norgate_export.py`; output `C:\norgate-export\<snapshot>\`; NDU database `C:\ProgramData\Norgate Data` |
| Destination | `EthanC100/em-macro-data` (private, owner only), branch `main`, folder `norgate/<snapshot>/` |

### Output format

- `contracts/<MARKET>/<CONTRACT>.csv` has the columns date,open,high,low,close,volume,open_interest.
  `close` is the settlement price. Prices are unadjusted and in exchange units, and no padding is
  applied.
- `coverage.csv` holds the checks for the 24 target markets. `all_markets.csv` lists every Norgate
  futures market.
- `manifest.csv` and `manifest.json` give each file's SHA-256 hash, size, row count and date range.
- The CSVs have CRLF line endings. The data repo's `.gitattributes` must contain `norgate/** -text`,
  so git never converts them and the hashes stay valid.

## Setup

### Secrets

These are SSM Parameter Store **SecureString** parameters in ap-southeast-2, encrypted with the
default `aws/ssm` key:

| Parameter | Contents |
|---|---|
| `/horizons/norgate/username` | Norgate username |
| `/horizons/norgate/password` | Norgate password |
| `/horizons/github/em-macro-data-token` | GitHub token with push access to `EthanC100/em-macro-data` |

The instance role (`AmazonSSMManagedInstanceCore` only) can read and decrypt them. The server reads
them with AWS CLI v2 into a variable and never prints them. Git gets the token through a temporary
`GIT_ASKPASS` helper that reads an environment variable, with `credential.helper` disabled, so the
token is never written to disk, a command line or the remote URL.

### Installing NDU

- The installer is `https://norgatedata.com/downloads/ndu.<version>.setup.exe`, an NSIS installer
  Authenticode-signed by NorgateData Pty Ltd.
- **Silent install (`/S`) does not work on a fresh machine.** It hangs on a hidden ".NET 4.7.2 is
  required" prompt, even when .NET 4.8 is installed. Its start-up reads optional registry values
  from a previous install, and when they are missing the installer's error flag stays set, which
  the .NET check then misreads.
- Started from SSM without `/S`, the wizard runs hidden in session 0. Its buttons can be pressed by
  sending window messages (`WM_COMMAND`/`BM_CLICK`) from PowerShell: accept the licence, keep the
  default folders, choose Update Automatically, Install, untick "Run", Finish. Because it runs as
  SYSTEM, NDU's per-user settings (`HKCU\Software\NDU`) land in SYSTEM's registry hive. They were
  copied to the Administrator profile.
- **NDU cannot run headless.** Started from SSM (session 0) it crashes immediately
  (`InvalidOperationException` in `Form.ShowDialog`). It must run in an interactive desktop session.

### Starting NDU (the one manual step)

After every start of the instance, NDU is not running. Someone has to:
1. RDP in as Administrator (RDP is allowed from the range in `aws_norgate_server.md`).
2. Start NDU from the desktop shortcut. It stays signed in.
3. Wait until the update finishes.
4. **Disconnect, without signing out**, so NDU keeps running.

`norgatedata` reaches NDU over its local API (`localhost:38889`), and this also works from SSM while
NDU runs in the disconnected session. To remove the manual step, the server would need an account
that logs in automatically and starts NDU. That is a security trade-off and has not been set up.

## How the script decides coverage

- A contract is **live** if its expiry date is after the as-of date, which is the date of the last
  Futures database update. For a live contract Norgate's `last_quoted_date()` returns the scheduled
  expiry date, not the date of its last bar. For an expired contract it returns the final bar.
- A market is **OK** when it has at least one expired contract, and the nearest live contract at
  least 12 months after the as-of month has a bar within 7 days of the as-of date. This proves the
  12-month deferred contract has current prices, not just a listing.
- Markets missing from Norgate are reported as missing, never substituted. Only alternative
  spellings of the same contract are tried (e.g. ICE Brent).

## Market availability

All 24 target markets are available in Norgate, with full history from the Futures subscription
(snapshot `2026-11_futures`, as of 2026-11-05). Every market has expired contracts, and a contract at
least 12 months out with a current settlement. "First year of data" is the year of the earliest
daily bar of any contract in that market, as Norgate supplies it.

| Market | Name | Norgate symbol | Exchange | Covered | First year of data |
|---|---|---|---|---|---|
| CL | WTI crude oil | CL | NYMEX | yes | 1983 |
| B | Brent crude oil | BRN | ICE Europe | yes | 1988 |
| HO | NY Harbor ULSD | HO | NYMEX | yes | 1978 |
| RB | RBOB gasoline | RB | NYMEX | yes | 2005 |
| NG | Henry Hub natural gas | NG | NYMEX | yes | 1990 |
| G | Low sulphur gasoil | GAS | ICE Europe | yes | 1988 |
| HG | Copper | HG | COMEX | yes | 1978 |
| GC | Gold | GC | COMEX | yes | 1978 |
| SI | Silver | SI | COMEX | yes | 1978 |
| PL | Platinum | PL | NYMEX | yes | 1978 |
| PA | Palladium | PA | NYMEX | yes | 1981 |
| ZC | Corn | ZC | CBOT | yes | 1978 |
| ZS | Soybeans | ZS | CBOT | yes | 1977 |
| ZW | Chicago SRW wheat | ZW | CBOT | yes | 1978 |
| KE | KC HRW wheat | KE | KCBT | yes | 1979 |
| ZM | Soybean meal | ZM | CBOT | yes | 1978 |
| ZL | Soybean oil | ZL | CBOT | yes | 1978 |
| SB | Sugar No. 11 | SB | ICE US | yes | 1978 |
| KC | Coffee C | KC | ICE US | yes | 1978 |
| CC | Cocoa | CC | ICE US | yes | 1979 |
| CT | Cotton No. 2 | CT | ICE US | yes | 1978 |
| LE | Live cattle | LE | CME | yes | 1978 |
| GF | Feeder cattle | GF | CME | yes | 1979 |
| HE | Lean hogs | HE | CME | yes | 1978 |

Norgate reports COMEX metals under NYMEX. Early contracts can predate the current contract
specification:
- HO was No. 2 heating oil before the switch to ULSD in 2013.
- The lean hog contract replaced live hogs in 1996, but HE history here starts in 1978.
- RB starts in 2005, when RBOB replaced unleaded gasoline. The earlier unleaded gasoline contract
  is not in Norgate's market list.

Check how Norgate defines a market's history before using its early data. Per-contract symbols,
ranges, counts, data notes and file sizes for each snapshot are in `COVERAGE.md` in the private
data repo.

### General data notes

- **Open interest lags one day.** On the latest bar, open interest is usually reported as 0 until
  the next update.
- **Many rows for far-deferred contracts are settlement only**: open = high = low = close with zero
  volume, because the contract did not trade that day.
- **No padding is applied.** If a contract has no bar on a day its market traded, the row is absent
  in Norgate's data, not filled in.

## Rerunning

1. Start the server and start NDU over RDP (see above):
   ```bash
   scripts/aws_server.sh start
   ```
2. Check that NDU is reachable over SSM. Expect `True` and today's date:
   ```powershell
   & 'C:\Program Files\Python312\python.exe' -c "import norgatedata as nd; print(nd.status(), nd.last_database_update_time('Futures'))"
   ```
3. Copy the current `scripts/norgate_export.py` to `C:\horizons-norgate\` (e.g. base64-encoded inside
   an SSM command), then run it:
   ```powershell
   $out = 'C:\norgate-export\2026-11_futures'      # one folder per snapshot
   Remove-Item -Recurse -Force $out -ErrorAction SilentlyContinue
   & 'C:\Program Files\Python312\python.exe' -I C:\horizons-norgate\norgate_export.py all --out $out
   ```
   `--markets CL GC` limits a run to some markets.
4. Push to the data repo from the server. The token comes from Parameter Store and is never printed:
   ```powershell
   $git = 'C:\Program Files\Git\cmd\git.exe'
   $env:GIT_TOKEN = & 'C:\Program Files\Amazon\AWSCLIV2\aws.exe' ssm get-parameter --region ap-southeast-2 `
       --name /horizons/github/em-macro-data-token --with-decryption --query Parameter.Value --output text
   '@echo off', 'echo %GIT_TOKEN%' | Set-Content C:\horizons-norgate\askpass.cmd -Encoding ascii
   $env:GIT_ASKPASS = 'C:\horizons-norgate\askpass.cmd'; $env:GIT_TERMINAL_PROMPT = '0'
   $repo = 'C:\horizons-norgate\em-macro-data'
   # first time: & $git -c credential.helper= clone https://x-access-token@github.com/EthanC100/em-macro-data.git $repo
   & $git -C $repo -c credential.helper= pull --quiet origin main
   & $git -C $repo config core.autocrlf false
   robocopy $out "$repo\norgate\2026-11_futures" /MIR /NFL /NDL /NJH /NJS /NP
   & $git -C $repo add -A; & $git -C $repo commit -m "Update Norgate futures export"
   & $git -C $repo -c credential.helper= push --quiet origin main
   Remove-Item C:\horizons-norgate\askpass.cmd; Remove-Item Env:GIT_TOKEN
   ```
   Then check the manifest hashes against a fresh clone. `/MIR` also deletes files that are no
   longer exported.
5. Stop the server: `scripts/aws_server.sh stop`.

## Licence obligations (NDU End User Licence Agreement 20261002)

- **Personal Use only.** No commercial or professional use, and no use on behalf of another person
  or organisation.
- Exports may be stored in private cloud and git hosting, but **no one else may have access**. Do not
  add collaborators to `em-macro-data` or make it public.
- **When the subscription ends, all exported data must be deleted** (clause 21), including copies
  and backups, and for git, its history. Only Derived Data may be kept, and only if it meets all
  four tests in the licence's definition: it cannot substitute for, resemble, be traced to, or be
  reverse-engineered back into the Content. Examples are backtest results and related statistics.
- The software may not be reverse engineered or decompiled.

## Build 0 follow-up export (T20–T22, A1 and A10)

This export completes Build 0 tests A1 and A10 (`results/T20-T22/build0.md`). Run it once, after NDU is started over
RDP as in "Starting NDU" above. It needs the current `scripts/norgate_export.py`, which adds the 10 financial targets
and the `metadata` subcommand.

| what | why | command (on the server, in PowerShell) |
|---|---|---|
| Daily contracts for 6E, 6B, 6M, FGBL, FOAT, FBTP and Long Gilt (LLG). 6L, 6Z and FBON are recorded as MISSING | A1 contract tables; A10 coverage | `python -I norgate_export.py all --markets financials --out C:\norgate-export\2026-11_financials` |
| Per-contract `first_notice_date`, `first_quoted_date`, `last_quoted_date` (scheduled expiry for live contracts), `point_value` and `tick_size` for all 34 markets | A1 metadata from the primary source (Build 0 used exchange rules for FND) | `python -I norgate_export.py metadata --out C:\norgate-export\2026-11_metadata` |

Notes on reading the output:
- **Coverage status GAP is expected for the financial futures.** They list fewer than 12 months ahead, so their
  status in `coverage.csv` reads GAP; this does not stop the export.
- **Check which metadata functions existed.** `metadata_fields.json` records which `norgatedata` functions were
  available and how many contracts returned errors. Physical commodity contracts should have a first notice date;
  cash-settled ones may not.

Push both folders to `em-macro-data` as `norgate/2026-11_financials/` and `norgate/2026-11_metadata/`, using step 4
of "Rerunning" with the folder names changed. **Do not `/MIR` over `norgate/2026-11_futures/`.**

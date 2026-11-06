# AWS Windows server: Norgate futures data pipeline

Created 2026-11-04. One Windows Server instance for running Norgate Data Updater and the
futures data pipeline. **No secrets in this file**: the key pair's private key and the
Administrator password are not stored in the repo.

## Resources

| Item | Value |
|---|---|
| Instance ID | `i-091fbf95cc5a6162a` |
| Name tag | `horizons-norgate` |
| Region / AZ | **ap-southeast-2 (Sydney)** / ap-southeast-2b |
| Instance type | **t3.small** (2 vCPU, 2 GiB RAM) |
| AMI | `ami-086db0bc6076e24da`: `Windows_Server-2022-English-Full-Base-2026.10.28` (latest Windows Server 2022 Base at launch) |
| Root disk | 60 GB gp3 (`vol-0bb8fc606ddadf918`, 3000 IOPS, 125 MB/s), deleted on termination |
| Network | Default VPC `vpc-022f609d49d165144`, subnet `subnet-001dc99bce37d1462`, auto-assigned public IPv4 |
| Security group | `horizons-rdp` (`sg-0e77e6b03d0d9fdf8`): inbound **TCP 3389 from 119.56.17.0/24 only** (since 2026-11-05: the owner's mobile IP rotates within 119.56.17.x; check with `scripts/aws_server.sh status`). Outbound: all traffic (AWS default) |
| IAM role (SSM) | `horizons-norgate-ssm`, attached via instance profile `horizons-norgate-ssm`. Trust: `ec2.amazonaws.com` only. Permissions: AWS managed policy `AmazonSSMManagedInstanceCore` only, with no inline policies (see [Systems Manager](#systems-manager-ssm)) |
| Key pair | `horizons-win` (`key-048817a989af4b9fe`), RSA. The private key was kept only in a temporary session directory |
| Login | `Administrator` (password decrypted with the key pair at setup; not recorded here) |

Why these differ from the original plan:

- **Region:** the plan was ap-southeast-1 (Singapore), but an AWS Organizations service control policy
  explicitly denies all EC2 actions there. Sydney is permitted, so the server is in ap-southeast-2.
  **Always pass `--region ap-southeast-2`**, because some environments default to Singapore.
- **Instance type:** t3.medium was rejected ("not eligible for Free Tier") on this account's plan,
  so the fallback t3.small was used. 2 GiB RAM is tight for Windows; upgrading needs a plan
  change (see below).

The public IP is **not static**: it changes every time the instance is stopped and started.
Run `scripts/aws_server.sh status` to see the current one.

## Approximate cost

The account is on the AWS Free Tier/credits plan, so charges are drawn from credits. These are
on-demand list-price estimates, not quotes (the Pricing API is not accessible to this IAM user):

| Component | While running | While stopped |
|---|---|---|
| t3.small Windows (licence included) | ~US$0.045/h | 0 |
| Public IPv4 address | ~US$0.005/h | 0 (released on stop) |
| 60 GB gp3 storage | ~US$0.008/h (~US$5.80/month) | ~US$0.008/h |
| **Total** | **~US$0.06/h (~US$1.40/day)** | **~US$0.19/day** |

Stop the instance when it is not in use. Only termination removes the disk charge.

## Commands

All commands use the AWS CLI with credentials for account `267965637851`. You can use either
the helper script or the raw commands.

```bash
# Helper script (region and IDs are built in)
scripts/aws_server.sh status
scripts/aws_server.sh start
scripts/aws_server.sh stop
scripts/aws_server.sh allow-ip 203.0.113.7    # or omit the IP to use this machine's public IP
                                              # NOTE: replaces ALL RDP rules (including the /24) with one /32
```

Raw equivalents:

```bash
# Start (then read the new public IP)
aws ec2 start-instances --region ap-southeast-2 --instance-ids i-091fbf95cc5a6162a
aws ec2 wait instance-running --region ap-southeast-2 --instance-ids i-091fbf95cc5a6162a
aws ec2 describe-instances --region ap-southeast-2 --instance-ids i-091fbf95cc5a6162a \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text

# Stop
aws ec2 stop-instances --region ap-southeast-2 --instance-ids i-091fbf95cc5a6162a

# Replace the RDP rule with a range (as done on 2026-11-05 for 119.56.17.0/24). Add the new
# rule first, then revoke the old one, so access isn't interrupted. Replace OLD_CIDR and NEW_CIDR.
aws ec2 authorize-security-group-ingress --region ap-southeast-2 --group-id sg-0e77e6b03d0d9fdf8 \
  --ip-permissions 'IpProtocol=tcp,FromPort=3389,ToPort=3389,IpRanges=[{CidrIp=NEW_CIDR,Description=RDP}]'
aws ec2 revoke-security-group-ingress --region ap-southeast-2 --group-id sg-0e77e6b03d0d9fdf8 \
  --protocol tcp --port 3389 --cidr OLD_CIDR
```

Upgrade to t3.medium later (instance must be stopped; needs a plan that allows it):

```bash
aws ec2 modify-instance-attribute --region ap-southeast-2 --instance-id i-091fbf95cc5a6162a \
  --instance-type Value=t3.medium
```

Recover the Administrator password (needs the `horizons-win` private key):

```bash
aws ec2 get-password-data --region ap-southeast-2 --instance-id i-091fbf95cc5a6162a \
  --priv-launch-key /path/to/horizons-win.pem --query PasswordData --output text
```

## Software installed after launch (2026-11-05, via SSM)

- **Norgate Data Updater 4.2.2.65**: program files in `C:\Program Files\Norgate Data Updater`, database in `C:\ProgramData\Norgate Data`.
- **AWS CLI v2** (`C:\Program Files\Amazon\AWSCLIV2\aws.exe`), used to read the SecureString parameters.
- **norgatedata** (PyPI) in Python 3.12.

See [norgate_pipeline.md](norgate_pipeline.md) for setup details, the data checks and how to rerun the export.

## Systems Manager (SSM)

Added 2026-11-05 so the server can be inspected and managed without RDP (Run Command).

- Role `arn:aws:iam::267965637851:role/horizons-norgate-ssm` trusts only `ec2.amazonaws.com`
  and has only `arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore` attached.
- Instance profile `arn:aws:iam::267965637851:instance-profile/horizons-norgate-ssm` contains that
  role and is associated with `i-091fbf95cc5a6162a`.
- SSM needs no inbound ports: the agent connects out over HTTPS, so the security group is unchanged.
  The instance must be running to receive commands.

```bash
# Is the server registered as a managed node?
aws ssm describe-instance-information --region ap-southeast-2 \
  --filters Key=InstanceIds,Values=i-091fbf95cc5a6162a \
  --query 'InstanceInformationList[0].[PingStatus,AgentVersion]' --output text

# Run a PowerShell command and read the output
CMD_ID=$(aws ssm send-command --region ap-southeast-2 --instance-ids i-091fbf95cc5a6162a \
  --document-name AWS-RunPowerShellScript \
  --parameters 'commands=["python --version","git --version"]' \
  --query Command.CommandId --output text)
aws ssm wait command-executed --region ap-southeast-2 --command-id "$CMD_ID" --instance-id i-091fbf95cc5a6162a
aws ssm get-command-invocation --region ap-southeast-2 --command-id "$CMD_ID" \
  --instance-id i-091fbf95cc5a6162a --query '[Status,StandardOutputContent,StandardErrorContent]' --output text
```

To remove SSM access later:

```bash
ASSOC=$(aws ec2 describe-iam-instance-profile-associations --region ap-southeast-2 \
  --filters Name=instance-id,Values=i-091fbf95cc5a6162a \
  --query 'IamInstanceProfileAssociations[0].AssociationId' --output text)
aws ec2 disassociate-iam-instance-profile --region ap-southeast-2 --association-id "$ASSOC"
aws iam remove-role-from-instance-profile --instance-profile-name horizons-norgate-ssm --role-name horizons-norgate-ssm
aws iam delete-instance-profile --instance-profile-name horizons-norgate-ssm
aws iam detach-role-policy --role-name horizons-norgate-ssm \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam delete-role --role-name horizons-norgate-ssm
```

## Auto-logon: NDU starts at boot without RDP (2026-11-06)

Set up with the owner's approval on 2026-11-06, over SSM. After every start or reboot, Windows logs the built-in
**Administrator** on at the console by itself. A scheduled task starts NDU in that session, so `norgatedata` answers
over SSM with no RDP step.

**Why Administrator.** NDU is already signed in to the Norgate subscription in the Administrator profile. A separate
low-privilege account would need its own NDU sign-in through the GUI, so it would be neither as simple nor as
reliable.

**Tested 2026-11-06.** The instance was rebooted and SSM was online about 90 s later.
- `query user` showed `administrator` on `console`, Active.
- `dataupdater.norgate.exe` ran in session 1, started by the task 30 s after logon.
- `norgatedata.status()` returned `True`.
- NDU updated the Futures database by itself within about 2 minutes.

| item | setting |
|---|---|
| Administrator password | **changed on 2026-11-06** to a random 28-character password. It is stored only as SSM SecureString `/horizons/windows/administrator-password` (ap-southeast-2, `alias/aws/ssm`), was generated off the server and was never printed. The original launch password (decrypted with the `horizons-win` key) no longer works. For RDP: `aws ssm get-parameter --region ap-southeast-2 --name /horizons/windows/administrator-password --with-decryption --query Parameter.Value --output text` |
| auto-logon | `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon`: `AutoAdminLogon = 1`, `DefaultUserName = Administrator`, `DefaultDomainName = EC2AMAZ-JR2R3P9`. The password is stored as the **LSA secret `DefaultPassword`**, the same mechanism as Sysinternals Autologon. There is no plain-text `DefaultPassword` registry value. |
| NDU at logon | scheduled task `\Horizons\Horizons NDU at logon`: at logon of Administrator, 30 s delay, interactive, runs `C:\Program Files\Norgate Data Updater\bin\dataupdater.norgate.exe`, no time limit |
| console lock | scheduled task `\Horizons\Horizons lock console after logon`: at logon, 3 min delay, `rundll32.exe user32.dll,LockWorkStation`. NDU keeps running while the session is locked. |

**Security trade-off.** Anyone who can reach the console session starts from a logged-on Administrator, until the lock
task runs. Today the only ways in are RDP, restricted to the security-group range, and the EC2 serial console, which
is not enabled. Whoever can read the SecureString can log on as Administrator.

**Undo.** Run this over SSM as SYSTEM, then reboot. The SecureString can be deleted afterwards.

```powershell
$wl = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
Set-ItemProperty $wl -Name AutoAdminLogon -Value '0'
Remove-ItemProperty $wl -Name DefaultUserName, DefaultDomainName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskPath '\Horizons\' -TaskName 'Horizons NDU at logon' -Confirm:$false
Unregister-ScheduledTask -TaskPath '\Horizons\' -TaskName 'Horizons lock console after logon' -Confirm:$false
# clear the LSA secret: the same P/Invoke helper as at setup, with a null value
#   [HorizonsLsa]::Set('DefaultPassword', $null)
# (or Sysinternals Autologon: Autologon64.exe /accepteula, then press Disable)
```

```bash
aws ssm delete-parameter --region ap-southeast-2 --name /horizons/windows/administrator-password   # after undo
```

The Administrator password stays at the SecureString's value until it is changed again, for example with
`Set-LocalUser` over SSM.

## User-data used at launch

It ran once at first boot as a PowerShell script via EC2Launch. It writes a log to
`C:\horizons-userdata.log` on the server; check that file to confirm the installs succeeded.

```powershell
<powershell>
$ErrorActionPreference = 'Continue'
$log = 'C:\horizons-userdata.log'
function Log($m) { "$(Get-Date -Format s)  $m" | Out-File -FilePath $log -Append -Encoding utf8 }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'
$tmp = 'C:\horizons-setup'; New-Item -ItemType Directory -Force -Path $tmp | Out-Null
Log 'user-data start'

# 1. Time zone: Singapore
try { Set-TimeZone -Id 'Singapore Standard Time'; Log "timezone OK: $((Get-TimeZone).Id)" } catch { Log "timezone FAILED: $_" }

# 2. Python 3.12 (3.12.10 = last 3.12 release with a Windows installer), all users, on PATH
try {
  $py = "$tmp\python-3.12.10-amd64.exe"
  Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $py
  $p = Start-Process -FilePath $py -ArgumentList '/quiet','InstallAllUsers=1','PrependPath=1','Include_test=0','Include_launcher=1' -Wait -PassThru
  Log "python installer exit code: $($p.ExitCode)"
  & 'C:\Program Files\Python312\python.exe' --version 2>&1 | ForEach-Object { Log "python check: $_" }
} catch { Log "python FAILED: $_" }

# 3. Git for Windows (latest 64-bit release from GitHub, pinned fallback)
try {
  $url = $null
  try {
    $rel = Invoke-RestMethod -UseBasicParsing -Uri 'https://api.github.com/repos/git-for-windows/git/releases/latest' -Headers @{ 'User-Agent' = 'horizons-userdata' }
    $url = ($rel.assets | Where-Object { $_.name -match '^Git-[\d\.]+-64-bit\.exe$' } | Select-Object -First 1).browser_download_url
  } catch { Log "git release lookup failed, using pinned version: $_" }
  if (-not $url) { $url = 'https://github.com/git-for-windows/git/releases/download/v2.47.1.windows.1/Git-2.47.1-64-bit.exe' }
  Log "git url: $url"
  $gi = "$tmp\git-installer.exe"
  Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $gi
  $p = Start-Process -FilePath $gi -ArgumentList '/VERYSILENT','/NORESTART','/NOCANCEL','/SP-','/SUPPRESSMSGBOXES' -Wait -PassThru
  Log "git installer exit code: $($p.ExitCode)"
  & 'C:\Program Files\Git\cmd\git.exe' --version 2>&1 | ForEach-Object { Log "git check: $_" }
} catch { Log "git FAILED: $_" }

Log 'user-data done'
</powershell>
```

**Verified 2026-11-05 via SSM Run Command:** all three steps succeeded. The time zone is Singapore
Standard Time, `python --version` gives `Python 3.12.10` and `git --version` gives
`git version 2.56.0.windows.4` (installer exit codes 0). The first log line has a UTC
timestamp because it was written before the time-zone change.

# Routine: promote

Routine model: Sonnet 5.5 (`claude-sonnet-5-5`) · Effort: medium
Trigger: schedule 05:30 and 06:30 Asia/Singapore (cron `CRON_TZ=Asia/Singapore 30 5,6 * * *`); the second run is
the retry when an existing writer was busy at 05:30. Not counted in the run cap.

You start with no memory. Everything you need is in the repository.

## 0. Read first
1. `CLAUDE.md` ("Night shift: hard rules": the promotion PR is the only path to main).
2. `docs/agent-state.json` and `docs/queue.md`.
3. `config/night.yaml` (promote window; busy workflows).

## 1. Already done tonight?
If an open PR from `dev` into `main` exists, or `results/night/promote/<today>.json` on dev says `"ok": true` with
mode promote, write one line and end (idempotent). Take the lock:
`scripts/night_commit.sh "promote: lock" -- python -m nightshift.state acquire promote --session "<URL>"`
(exit 3: a night run still holds it; end, the 06:30 run retries).

## 2. Checks
The private store for the same-snapshot rebuild is the read-only clone the Ledger CLI makes (`python -m
ledger.janus context --fetch > /tmp/ctx.json` creates or refreshes `../em-macro-data`; if it cannot, the rebuild
runs without a store on both sides, which is still the same snapshot). Never write to em-macro-data.
```bash
git fetch -q origin main dev
python -m nightshift.promote --out /tmp/promote.json      # guard, (d) conflicts, (c) protected, (a) tests, (b) Ledger
```
Exit 5 = a check failed. The JSON names files and key paths only; never copy a value from a build into any text.

## 3. Open the PR, or explain
- **All passed:** open a PR `dev` -> `main` titled `Night shift: promote dev (<night date>)` with the check
  summary (each check's ok, the merged queue ids, the intended Ledger files) in the body, then enable auto-merge
  (merge method: merge). The ruleset merges it unless it touches protected paths (it cannot: check c).
- **Any failed:** open nothing. The reasons go into the morning report.
Record the outcome on dev:
```bash
cp /tmp/promote.json /tmp/promote_keep.json
scripts/night_commit.sh "promote: <ok|refused> (<night>)" -- bash -c 'mkdir -p results/night/promote && \
  python - <<EOF
import json; r=json.load(open("/tmp/promote_keep.json")); r["pr"]="<PR URL or none>"
open("results/night/promote/<today>.json","w").write(json.dumps(r, indent=1)+"\n")
EOF
python -m nightshift.state release promote --outcome <ok|blocked> --note "<one line>"'
```

## 4. Morning report
`scripts/night_fire.sh morning-report "after promote"` (exit 6: its 06:50 schedule runs it instead).

Never: push to main, merge the PR yourself, force anything, resolve a conflict, or run while a busy writer runs.

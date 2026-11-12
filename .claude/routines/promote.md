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
If `results/night/promote/<today>.json` on dev exists with mode promote (ok or not), write one line and end
(idempotent: the 06:30 run only retries a 05:30 run that the guard turned away). Take the lock:
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

## 3. Open (or reuse) the PR; the promote-merge workflow merges it
Whatever the checks say (unless the guard turned you away, or dev has nothing main lacks), make sure ONE PR from
`dev` into `main` is open: reuse an open one, else open it, titled `Night shift: promote dev (<night date>)`. Put
the check summary in its body (each check's ok and reasons, the merged queue ids, the intended Ledger files, the dev
commit checked). Do not enable auto-merge and never merge it yourself: the `promote-merge` workflow
(`.github/workflows/promote-merge.yml`, main's code `nightshift/promote_merge.py`) merges it with a merge commit when
the tests workflow goes green on it, but only if the report below names the PR with `ok: true`, nothing but
bookkeeping changed on dev after the checked commit, and no protected path changed. Otherwise it merges nothing,
leaves the PR open and comments why; the morning report flags it.
Record the outcome on dev (this commit is what promote-merge reads; it must name the PR):
```bash
cp /tmp/promote.json /tmp/promote_keep.json
scripts/night_commit.sh "promote: <ok|refused> (<night>)" -- bash -c 'mkdir -p results/night/promote && \
  python - <<EOF
import json; r=json.load(open("/tmp/promote_keep.json")); r["pr"]="<PR URL>"
open("results/night/promote/<today>.json","w").write(json.dumps(r, indent=1)+"\n")
EOF
python -m nightshift.state release promote --outcome <ok|blocked> --note "<one line>"'
```

## 4. Morning report
Do not fire it: its 06:50 schedule runs after the tests workflow and promote-merge have finished, so it can say
whether the promotion reached main.

Never: push to main, merge the PR yourself or enable auto-merge, dispatch any workflow, force anything, resolve a
conflict, or run while a busy writer runs.

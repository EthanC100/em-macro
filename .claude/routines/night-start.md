# Routine: night-start

Routine model: Sonnet 5.5 (`claude-sonnet-5-5`) · Effort: medium
Trigger: schedule, daily 22:30 Asia/Singapore (cron `CRON_TZ=Asia/Singapore 30 22 * * *`). Not counted in the run cap.
Subagents: triage (Sonnet 5.5, medium), opposition (Opus 5.5, high).

You start with no memory. Everything you need is in the repository.

## 0. Read first, in this order
1. `CLAUDE.md`, especially "Night shift: hard rules". They override everything below.
2. `docs/agent-state.json` (`python -m nightshift.state status`) and `docs/queue.md`.
3. `config/night.yaml` (window, cap, safe mode, busy workflows).
`pip install -q -r requirements.txt` if a module is missing. Scratch files go in `/tmp`, never in the repository.

## 1. May the night start?
`python -m nightshift.guard check night-start`. If it says no (outside the window, or an existing writer such as
ledger-daily, the rebalance or the Janus daily review is running), do not wait in a loop: end with one line. The
first hourly night-worker run does steps 2-5 itself when tonight has no night-start entry in the state log.

## 2. Sync dev with main (never the other way)
```bash
git fetch -q origin main dev || git fetch -q origin main
git checkout -q -B dev origin/dev 2>/dev/null || git checkout -q -B dev origin/main
python -m nightshift.merge main-into-dev --main origin/main
```
`nightshift.merge` resolves only the night shift's own files: `docs/queue.md` rows by id (most advanced status
wins), `docs/agent-state.json` and `results/opposition/calibration.csv` from dev. It prints JSON and exits:
- 0 (`merged` or `up-to-date`): `git push origin dev` (dev only; never main). Name any `auto_resolved` files in
  the run note.
- 3 (`conflict`: another file conflicts) or 4 (`invalid-queue`): it has already run `git merge --abort`. **Never
  resolve a conflict by hand.** Stop the chain: `scripts/night_commit.sh "night-start: chain stopped (dev
  conflicts with main)" -- python -m nightshift.state stop --reason "dev conflicts with main: <not_auto files or
  queue errors>"` and end.
- 2 or anything else: stop the chain the same way with the error text, and end.

## 3. Triage
Use the Agent tool with `subagent_type: triage`. Pass it nothing but "Audit em-macro for tonight's queue; return
your JSON findings". For each finding that has quoted evidence, reproduces on dev, is not already in
`docs/queue.md`, and does not need a protected path (those become type `research`), file it:
write the evidence to `/tmp/ev_<n>.md`, then add it through the script in step 5.

## 4. The Opposition on every unreviewed item
For each `proposed` item of type bug, data or lab whose `opposition` cell is empty (including the ones just
filed), call the Agent tool with `subagent_type: opposition`, giving it the row and its evidence section. Then:
- `opposition` cell = `no block, p=NN%` (verdict advisory) or `BLOCK (x): <reason>`;
- log it: `python -m nightshift.logs opposition --target-type queue --target-id Qnnn --p-works NN --verdict
  <advisory|BLOCK-x> --model claude-opus-5-5`.
Research items: if it needs a pre-registration, the explorer drafts one later; never approve research.

## 5. Write the queue and state to dev
All writes go through one command so they land on dev together:
```bash
cat > /tmp/night_start.sh <<'EOF'
set -e
python -m nightshift.queue add --type <t> --title "<title>" --acceptance "<test>" --ledger-diff "<files|none>" --evidence-file /tmp/ev_1.md
python -m nightshift.queue set Q0nn opposition "no block, p=60%"
python -m nightshift.logs opposition --target-type queue --target-id Q0nn --p-works 60 --verdict advisory --model claude-opus-5-5
python -m nightshift.queue auto-approve
python -m nightshift.queue validate
EOF
scripts/night_commit.sh "night-start: triage and Opposition review" -- bash /tmp/night_start.sh
```

## 6. Start the chain
`python -m nightshift.guard next` gives `night-worker`, `night-explorer` or `stop`.
- worker/explorer: `scripts/night_fire.sh <routine> "chained from night-start"`. If it exits 6 (no API trigger in
  this environment), say so: the hourly schedules of night-worker and night-explorer pick it up.
- stop: `scripts/night_commit.sh "night-start: nothing to do" -- python -m nightshift.state stop --reason "<why>"`.

Record the run: `scripts/night_commit.sh "night-start: done" -- python -m nightshift.state release night-start --outcome ok --note "<sync result; filed/approved/blocked>"`.
End with three lines: dev sync result, items filed/approved/blocked, what was fired.

# Manhattan operations: the steps only Ethan can take

Session 7M, 2026-11-13. Each step is a settings change, a secret, spending, a protected path or a decision, which no
session may take (CLAUDE.md rules 2, 11, 16). Nothing here was created, changed, enabled or dispatched by a session.
Order: 1 to 4 make the runner able to write; 5 to 7 make a blind batch possible; 8 and 9 are the switches. The
general list stays [../ETHAN_ACTIONS.md](../ETHAN_ACTIONS.md) (not edited by this session, to avoid clashing with
the parallel 6M session); its items 2, 3 and 7 are the ones these steps carry out.

## 1. Create the private ledger repository

GitHub, New repository: owner `EthanC100`, name `manhattan-ledger`, **Private**, no README (an empty repository).
Do not add it to any Claude Code environment.

## 2. The runner's deploy key and secret

On your own machine (not in a session):

```bash
ssh-keygen -t ed25519 -N "" -C "manhattan-ops-runner" -f ~/manhattan_ledger_deploy
```

- `manhattan-ledger` -> Settings -> Deploy keys -> Add: paste `~/manhattan_ledger_deploy.pub`, tick **Allow write
  access**.
- `em-macro` -> Settings -> Environments -> New environment `manhattan-ledger`. Under **Deployment branches and
  tags** choose **Selected branches and tags** and add `main` only. (Optional: add yourself as a required reviewer;
  every run then waits for your approval.)
- In that environment (not as a repository secret): **Add environment secret** `MANHATTAN_LEDGER_DEPLOY_KEY` = the
  contents of `~/manhattan_ledger_deploy` (the private key). Then delete the local private key file, or keep it only
  in your password manager.

  Why an environment: repository secrets reach a manually dispatched run on **any** branch. A session that can push a
  branch could edit this workflow there, remove its main-only guard and dispatch it. Environment secrets restricted to
  `main` never reach such a run. This holds only while `main` itself is protected (ETHAN_ACTIONS item 6).
- Check GitHub's ed25519 host key in the workflow against docs.github.com ("GitHub's SSH key fingerprints").

## 3. Keep every session away from it

- github.com -> Settings -> Applications -> Claude -> Configure: under repository access choose **Only select
  repositories** and do **not** include `manhattan-ledger`. (If the App is set to "All repositories", any session's
  `add_repo` could reach it.)
- In claude.ai, check that no Claude Code environment lists `manhattan-ledger` as a source.
- Optional, if you have GitHub Pro: a ruleset on `manhattan-ledger` `main` blocking force pushes and deletions
  (without Pro, private repositories have no rulesets; tamper evidence then rests on the chain, the published head
  and the mirror: [LEDGER.md](LEDGER.md)).

## 4. Choose the mirror

Recommended: **A** a private repository on Codeberg or GitLab.com, plus **B** the iMac pulling nightly
([LEDGER.md](LEDGER.md), "Mirror"). For A:

- create the private repository there and add a deploy key with write access (a second key pair, as in step 2);
- **environment** secret `MANHATTAN_MIRROR_DEPLOY_KEY` (in `manhattan-ledger`) = that private key;
- environment **variables** (in `manhattan-ledger`): `MANHATTAN_MIRROR_HOST` (for example `codeberg.org`),
  `MANHATTAN_MIRROR_KNOWN_HOSTS` (the host's line from `ssh-keyscan -t ed25519 codeberg.org`, checked against the
  provider's published fingerprint), `MANHATTAN_MIRROR_URL` = `ledger-mirror:<you>/manhattan-ledger-mirror.git`.

Without a mirror the runner reports `mirror_status: not-configured` and still runs.

## 5. The blind-generator environment

Create a private repository `manhattan-blind` with the files listed in [BLIND_GENERATOR.md](BLIND_GENERATOR.md), and a
Claude Code cloud environment with that repository only, **network access: none**, no connectors, no setup script,
no variables. Write `tools.txt` from the tool list the session shows.

## 6. Install the critic

Copy [drafts/manhattan-critic.md](drafts/manhattan-critic.md) to `.claude/agents/manhattan-critic.md` on main
(`.claude/` is protected, so this is your edit). Read it first: it reads one file, `critic_input.json`, and has the
Read tool only.

## 7. Run the isolation kit in the blind environment

Inside a session of the step-5 environment:

```bash
python3 isolation_kit.py --declared-tools tools.txt --allowed-remote manhattan-blind --json out/isolation.json
```

Proceed only on `PASS`. If `clone_access` or `network` fails because the session's git proxy still serves public
GitHub, the environment is not blind: use the tool-less API call instead (ETHAN_ACTIONS item 3, spending).

## 8. Protect the ops switches

Add to the protected block of `.github/CODEOWNERS` on main, above `# protected:end`:

```
# Manhattan ops: the promotion gate, the blind template and its hash, the runner workflow
/manhattan/ops/promotion.py @EthanC100
/manhattan/ops/templates/ @EthanC100
/.github/workflows/manhattan-ops-runner.yml @EthanC100
```

Promotion stays off until you add a validated protocol's SHA-256 to `ADOPTED_PROTOCOLS` in
`manhattan/ops/promotion.py` **and** set `claims.enabled: true` in `config/manhattan.yaml`.

## 9. Enable the runner

When steps 1 to 4 are done and this branch is merged:

1. Actions -> manhattan-ops-runner -> Run workflow (from main), once, by hand. The log shows one health line with
   `status: ok` (or `partial` with `mirror-status: not-configured`). With no batch yet it only captures FRED data.
   This first run is also the first real test of the FRED fetcher.
2. To schedule it, uncomment the two `schedule` lines in the workflow on main. Watch the first week's
   `missed_runs` in the health record: this repository's schedules start late (Q018).

## Not needed for the first cycle

The iMac runner, licensed data, the reserve fence (`reserve.enabled` stays false) and any spending.

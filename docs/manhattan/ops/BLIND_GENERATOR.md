# The blind generator: template, environment, procedure

Code: `manhattan/ops/templates/blind_v2.md` (the prompt; its SHA-256 is in `templates.sha256`),
`manhattan/ops/mockgen.py` (`blind_request`: the only way to fill it), `manhattan/ops/isolation_kit.py`.
No real hypothesis has been generated. The only generator run so far is a mock that returns families labelled
SYNTHETIC, in tests.

## What "blind" means here, and what it cannot mean

A blind-channel generator writes hypotheses without access to any Manhattan result, ledger, repository or the web.
**Model pretraining cannot be removed by isolation.** The model has read market history and papers up to its
training cutoff, possibly including this public repository. A blind-channel hypothesis is therefore blind to
**Manhattan's results**, not to history the model has read. This is why historical screening is only a filter
(Protocol v3 §4) and why every claim at 5% rests on forward data dated after the freeze.

## Template (prompt v2)

`blind_v2.md` asks for families and hypotheses in JSON. Version 2 adds to version 1 (`manhattan/templates/blind_v1.md`,
unchanged): a structured `signal` (kind and fixed parameters), the natural `frequency`, `grid_justification` (an
economic reason and a mechanism range for every varied parameter), `budget_justification` above 16 variants, and
`timing` (calendar, horizon, execution lag, data cutoff). `blind_request(n_families, max_hypotheses, domains)`
fills it; there is no argument through which a result, a path or free text could reach the prompt. A template change
is a new file and a new hash, never an edit.

## The environment: a separate repository, `manhattan-blind`

Contents (nothing else; the isolation kit fails on any other file, on history holding any other file, and on a
second branch):

```
README.md          how to run one batch (below)
PROMPT_v2.md       the filled prompt for this batch: produced by blind_request on em-macro, copied in by Ethan
schema.json        optional: a JSON schema of the reply
isolation_kit.py   a copy of manhattan/ops/isolation_kit.py
tools.txt          the session's tool names, one per line, written by Ethan from the session's tool list
out/               where the reply is saved (out/reply.json)
.gitignore
```

Cloud environment settings (Ethan's, ETHAN_OPS_ACTIONS step 5): this repository only; network access **none**; no
connectors; no setup script; no environment variables or secrets; the Claude GitHub App not given em-macro,
em-macro-data or manhattan-ledger for this environment. No `CLAUDE.md`, no `.claude/` directory, no memory.

The strongest alternative is a tool-less API call from the iMac (ETHAN_ACTIONS item 3): the model then reads
nothing at all. It needs an API key, which is spending.

## Procedure for one batch

1. On em-macro: `blind_request(...)` -> `PROMPT_v2.md` (its hash and the template hash are recorded in the manifest).
2. Ethan copies `PROMPT_v2.md` into `manhattan-blind` and starts a session in the blind environment.
3. **First** the session runs `python3 isolation_kit.py --declared-tools tools.txt --allowed-remote manhattan-blind`.
   Only on `PASS` does it go on. On `FAIL` or `INCOMPLETE`, stop; the batch is not blind.
4. The session answers the prompt into `out/reply.json`, with no other step.
5. Ethan copies `out/reply.json` to em-macro. `python -m manhattan.ops.freeze_pr --critic-input-only` writes the
   critic input; the critic agent reviews it; `freeze_pr` prepares the manifest pull request.

## Isolation checklist (each channel the kit checks)

| channel | closed when | checked by |
|---|---|---|
| network | no TCP connection to GitHub, PyPI, FRED, Anthropic, Google or public DNS; no reachable proxy; no DNS resolution | kit: `network` |
| clone access | `git ls-remote` fails for em-macro, em-macro-data and manhattan-ledger over HTTPS and SSH | kit: `clone_access` |
| files outside the repository | the home directory holds only shell defaults; no other git repository and no path named like Manhattan, em-macro, ledger or Janus under `/workspace`, `/mnt`, `/data`, `/srv`, `/opt`, `/home`, `/root`; no such mount | kit: `files_outside_repo` |
| leftover artifacts and caches | the repository holds only the allowed files; no `data/`, `results/`, `__pycache__`; `~/.local/share` empty | kit: `leftover_artifacts` |
| environment variables and credential helpers | no variable named like a token, key, secret, proxy or GitHub setting; no `.git-credentials`, `.netrc`, `gh` login, SSH key, cloud credentials; no git credential helper, extra header or URL rewrite | kit: `credentials` (names only) |
| tools and MCP servers | no MCP server or plugin configured; the declared tools within Read, Write, Edit, Glob, Grep | kit: `tools_and_mcp` (needs `tools.txt`) |
| inherited context | no `CLAUDE.md`, `AGENTS.md` or `.claude/` in the repository or above it; no `~/.claude` agents, skills, commands, plugins, memory; no past-conversation transcripts | kit: `inherited_context` |
| indirect channels | empty shell histories; empty temporary directories; no Manhattan-named file in package caches; only the generator repository as remote, one branch, no stash, nothing else in history | kit: `indirect_channels` |
| pretraining | **cannot be closed** | stated, not checked |

**This session (a build session) fails every channel**, as expected and recorded in OPS_PROGRESS.md: open network
through the agent proxy, em-macro readable by `git ls-remote`, tokens in the environment, a past-conversation
transcript, CLAUDE.md and `.claude/` in the repository, tools beyond the allowed set.

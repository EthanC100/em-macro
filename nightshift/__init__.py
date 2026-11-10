"""The night shift: autonomous overnight agents that work on the `dev` branch (docs/agent-system.md).

Nothing in this package writes to `main`, to `data/ledger/`, `data/janus/`, `results/shadows/` or to em-macro-data.
The only path to `main` is the promotion pull request, which `nightshift.promote` checks first.
"""

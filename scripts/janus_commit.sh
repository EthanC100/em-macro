#!/usr/bin/env bash
# Earlier name of scripts/ledger_commit.sh (the Janus runbooks use it); same arguments, same behaviour.
exec "$(dirname "$0")/ledger_commit.sh" "$@"

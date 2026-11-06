# em-macro: notes for Claude Code sessions

- **Pasted ledger blocks.** If I paste a block that starts with `DECISION RECORD`, `FORECAST` or `RESOLVE`, follow
  [docs/ledger/clerk.md](docs/ledger/clerk.md). Show me the Risk Manager result (`python -m ledger.clerk check`), then
  log it with `python -m ledger.clerk log` and give me the new id. Never edit `data/ledger/` by hand.
- **Janus sessions** follow [docs/janus/quick_check.md](docs/janus/quick_check.md) and
  [docs/janus/daily_review.md](docs/janus/daily_review.md). The forecast resolver follows
  [docs/ledger/forecast_resolver.md](docs/ledger/forecast_resolver.md). In a Janus session, the CLI reads futures
  settlements through a read-only clone of em-macro-data made with `DATA_REPO_READ_TOKEN`. Never print that token,
  and never write to em-macro-data.

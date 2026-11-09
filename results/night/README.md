# Night shift outputs

- `morning/YYYY-MM-DD.md`: the morning report (`python -m nightshift.morning`).
- `promote/YYYY-MM-DD.json`: the promotion checks of that morning (`python -m nightshift.promote`): which checks
  passed, the merged queue ids, and the names (never the values) of any Ledger data that differed.

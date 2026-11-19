# S16 acceptance reports

Machine-readable output of `python tests/acceptance/run.py` (schema `manhattan.s16.acceptance/1`) and
`tests/acceptance/mutation_check.py` (schema `manhattan.s16.mutations/1`). Spec and readiness criteria:
`docs/manhattan/acceptance/S16_ACCEPTANCE.md`.

| file | tree | result |
|---|---|---|
| `main.json` | main `9b24bd7` with only the acceptance suite added | 5 PASS, 51 BLOCKED, NOT_READY |
| `integration_5pr.json` | local scratch merge of PR heads #84 `e1882be`, #85 `3f6b213`, #86 `bab1a4d`, #87 `8c210a0`, #89 `232d0d6` onto main `9b24bd7` (never pushed) | 49 PASS, 7 BLOCKED (GAP-01 to GAP-07), NOT_READY |
| `mutations_integration_5pr.json` | the same scratch tree | 13 of 13 planted defects caught |

These reports are synthetic acceptance results only: `scientifically_verified` is always false. Nothing here was
produced from real, licensed, reserve or forward data, and no file here is read by any writer or workflow.

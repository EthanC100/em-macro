# S16 phase 2 acceptance reports (HTE integration adapters)

Spec: `docs/manhattan/acceptance/S16_PHASE2_ADAPTERS.md`. Schemas as in `../README.md`.

| file | tree | result |
|---|---|---|
| `main.json` | this branch: main `9b24bd7` + the S16 suite, no Manhattan PR merged | 6 PASS, 97 BLOCKED, NOT_READY |
| `integration_7pr.json` | local scratch merge (never pushed): main `37e3eb4` + #84 `e1882be`, #85 `3f6b213`, #86 `bab1a4d`, #87 `8c210a0`, #90 `e64397d` (includes #89 `232d0d6`), #93 `50caa18` | 78 PASS, 25 BLOCKED (every real-adapter ACC86/DEX93 case, GAP-01 to GAP-07), NOT_READY |
| `mutations_integration_7pr.json` | the same scratch tree | 28 of 28 mutations caught (M01-M13, MX01-MX08, MO1-MO5, MU1-MU2) |

`ORC-*` results come from a test-only oracle and never stand for the adapters. `scientifically_verified` is always
false; nothing here was produced from real, licensed, reserve or forward data.

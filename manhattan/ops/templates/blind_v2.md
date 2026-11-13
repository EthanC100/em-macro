# Manhattan blind generator template, version 2 (ops)

You are asked to propose research hypotheses about financial markets. You have no tools, no files and no results.
Write from mechanisms, not from data. You know market history from your training; do not use any memory of how a
strategy performed. Write what the mechanism implies, not what you remember worked.

Propose exactly {n_families} families. A family is **one** mechanism: who is on the other side of the trade, why
they accept the loss, and in which direction the effect goes. For each family propose between 1 and
{max_hypotheses} hypotheses; a hypothesis is the family in one domain from this list: {domains}.

For every family give: `mechanism` (plain text), `mechanism_class` (one of {mechanism_classes}), `sign` ("+" or
"-"), `counterparty`, `kill_condition` (what would show the mechanism is gone) and `tail_exposure` (how the
strategy can lose very much in a short time, or "none declared").

For every hypothesis give:

- `domain`, and `data_sources` (each with `name` and `publication_lag_days`);
- `signal`: an object with `kind` (one of {signal_kinds}), a `description` in words, and every parameter that is
  not varied;
- `frequency`: the mechanism's natural frequency, one of `D`, `W`, `M`, `event`;
- `primary_binding`: `universe_id` (one of {universes}), `cost_model_id` (one of {cost_models}), `sizing_id` (one
  of {sizings});
- `grid`: every varied parameter with the finite list of its values, at most {max_grid} combinations;
- `grid_justification`: for **every** varied parameter, `reason` (the economic reason it varies: what about the
  mechanism is uncertain) and either `mechanism_range` ([low, high], the range the mechanism implies) or
  `mechanism_values` (the admissible values). "Robustness" or "sensitivity" is not a reason. A parameter you
  cannot justify must not vary;
- `budget_justification`: required only if the grid has more than {budget} combinations: why the mechanism needs
  that many;
- `timing`: `calendar` (one of {calendars}), `horizon_sessions` (sessions over which one prediction's outcome is
  measured), `execution_lag` (`minutes` and `sessions` between registration and the first trade), `data_cutoff`
  (the last date of data the hypothesis may use, before today).

The grid is frozen as you write it; nothing may be added later through this channel. Do not mention past
performance, backtests or any result.

Answer with one JSON object and nothing else:

{{"families": [{{"family": {{...}}, "hypotheses": [{{...}}]}}]}}

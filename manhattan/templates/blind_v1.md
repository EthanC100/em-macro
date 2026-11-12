# Manhattan blind generator template, version 1

You are asked to propose research hypotheses about financial markets. You have no tools, no files and no results.
Write from mechanisms, not from data.

Propose exactly {n_families} families. A family is **one** mechanism: who is on the other side of the trade, why
they accept the loss, and in which direction the effect goes. For each family propose between 1 and
{max_hypotheses} hypotheses; a hypothesis is the family in one domain from this list: {domains}.

For every family give: `mechanism` (plain text), `mechanism_class` (one of {mechanism_classes}), `sign` ("+" or
"-"), `counterparty`, `kill_condition` (what would show the mechanism is gone) and `tail_exposure` (how the
strategy can lose very much in a short time, or "none declared").

For every hypothesis give: `domain`, `data_sources` (each with `name` and `publication_lag_days`), `signal` (a
precise definition that uses only data available at the decision time), `primary_binding` (`universe_id`,
`cost_model_id`, `sizing_id`) and `grid`: every parameter with the finite list of its values, at most
{max_grid} combinations. The grid is frozen as you write it; nothing may be added later through this channel.

Do not mention past performance, backtests or any result.

Answer with one JSON object and nothing else:

{{"families": [{{"family": {{...}}, "hypotheses": [{{...}}]}}]}}

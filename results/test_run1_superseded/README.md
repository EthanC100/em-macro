# Superseded first hold-out run

This is the first evaluation of the 2022+ hold-out, kept for transparency.
After it ran, a data-alignment bug was found: when a country's FX or yield
series had no observation after the base day (e.g. FRED's BRL series ending
on 2026-10-23, or a US holiday on the Monday after a Sunday election), the
window end silently reused the base-day price, giving a spurious 0.00 move.
The fix (window ends must be dated after the base observation for the
country's own series) changed two fit-sample rows (EL_BR_20181007 FX day 1,
RD_ID_20080805 FX) and nothing in the trading-rule direction. Fit and hold-out
were then re-run once; `results/test/` holds that run. Conclusions are the
same in both runs.

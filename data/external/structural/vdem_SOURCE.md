# vdem.csv — judicial independence and governance (V-Dem)

Downloaded: 2026-10-29. Rows: 13 countries x 2005–2025 (273 rows, no missing values). Key: `iso3, year` (V-Dem `country_text_id`).

**Dataset:** V-Dem Country-Year dataset (Full+Others), **v16** (Coppedge et al. 2026, doi:10.23696/vdemds26).
**Route used:** the full download on v-dem.net sits behind a form, so I used the official keyless distribution, the V-Dem Institute's `vdemdata` R-package repository: https://github.com/vdeminstitute/vdemdata, file `data/vdem.RData` (package Version 16.0, commit f4dd26922e658442524dfd954bf14f7ebe622d5d "v16 release", 2026-03-17). R is not available here, so I read it with the Python package `pyreadr`. The variable definitions below come from `data/codebook.RData` in the same repo.

| column | V-Dem name | definition / scale |
|---|---|---|
| `v2x_jucon` | Judicial constraints on the executive index | Does the executive respect the constitution and comply with court rulings, and can the judiciary act independently? Interval 0–1, higher = more constraint |
| `v2juhcind` | High court independence | How often do high-court rulings in government-salient cases merely reflect government wishes? Ordinal 0–4 (0 = always … 4 = never), reported as the **measurement-model latent point estimate** (unbounded, roughly −5..5), higher = more independent |
| `v2juncind` | Lower court independence | Same question for lower courts. Same latent scale |
| `v2x_rule` | Rule of law index | Interval 0–1, higher = stronger rule of law |
| `v2x_corr` | Political corruption index | Interval 0–1, **higher = MORE corrupt** |
| `v2x_polyarchy` | Electoral democracy index | Interval 0–1 |
| `version` | `v16` | |

Caveats: the latent `v2juhcind`/`v2juncind` estimates are re-estimated each release, so do not mix them across V-Dem versions. The most recent years can be revised in later releases. Türkiye is `TUR`.

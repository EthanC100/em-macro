# Ledger reports

One file per report, Markdown (`.md`) or PDF (`.pdf`), named `YYYY-MM-DD_slug.md`.
Every Markdown report starts with a front-matter header:

```
---
date: 2026-11-03
title: Weekly review, week 45
type: weekly review        # daily briefing | weekly review | monthly notebook | research | other
country: Brazil            # optional; "Global" or blank if none
---
```

A PDF report carries the same header in a sidecar file with the same name and the
extension `.meta.yml` (the Report issue form writes both). Files in this folder are
normally written by the Report issue form (`.github/ISSUE_TEMPLATE/report.yml`), but a
file committed by hand with the header above is picked up by the next build as well.
The `results/*.md` write-ups of this repository are also listed in the app, under
type "research". This README is not a report.

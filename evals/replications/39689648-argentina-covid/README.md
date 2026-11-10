# PMID 39689648: Argentina COVID-19

This reconstruction follows the paper's national ecological design. It uses the
official Ministry of Health COVID-19 line list for 1 March through 31 December
2020 and AERIS/OpenAQ PM2.5 records. It does not use the paper's ACAG PM2.5
values.

## Public inputs

- Outcomes: Argentina Ministry of Health historical case archive, `Covid19Casos.zip`.
- Department identifiers and centroids: Argentina Georef API.
- Department boundaries: geoBoundaries ARG ADM2, 2020 release.
- Exposure: OpenAQ v3 with AERIS historical S3 fallback.

`manifests/public_inputs.json` records URLs, checksums, and retrieval time.

## Workflow

```bash
PYTHONPATH=. \
  python scripts/acquire_public_inputs.py
PYTHONPATH=. \
  python scripts/build_outcomes.py
PYTHONPATH=. \
  python scripts/prepare_boundaries.py
PYTHONPATH=. \
  python scripts/run_aeris_exposure.py
```

The exposure runner checkpoints each department. The strict primary estimand is
the mean of OpenAQ PM2.5 monitor means inside a department boundary over the
outcome window. `run_aeris_centroid_fallback.py` provides a separately labeled
25 km representative-point sensitivity for strict no-station records.

## Status

The official outcome aggregation and coded-boundary join are complete. The
strict AERIS department pass is running. `RESULT.md` is updated only after it
produces a fit-ready panel.

# PMID 38788590: Brazil cancer mortality

This directory is an independent, source-substitution replication attempt of Yu et al. (2024), PMID 38788590. It uses only public mortality outcomes and reconstructs exposure with AERIS. It never reads the authors' PM2.5 values.

## Bounded reproduction target

The published analysis covers 5,570 Brazilian municipalities from 2000-2019. This executable first targets Sao Paulo municipality in calendar year 2019, the last year of the published period. The geographic and temporal restriction is necessary to make a public, inspectable first run practical; it is not a national reproduction.

The outcome definition is the paper's explicit union of cancer ICD-10 codes. The analysis creates a time-stratified case-crossover data set: each death date is compared with other dates on the same weekday in the same month. The fitted conditional likelihood uses the published lag 0-2 PM2.5 exposure, temperature, relative humidity, and a national-holiday indicator. Temperature is represented by a linear 3-day mean rather than the paper's distributed-lag cross-basis, so this is an approximation even if all inputs are available.

## Data sources

The complete URL and access record is in `source_manifest.json`. Download and
run records are written beside each generated input under `data/raw/` and
`data/derived/`.

- SIM death microdata: public DATASUS `DOSP2019.dbc`, filtered to Sao Paulo municipality residents.
- Boundary: public IBGE municipality polygon, code `3550308`.
- Exposure discovery: AERIS `estimate_boundary_exposure`, using OpenAQ monitor metadata within the IBGE polygon.
- Exposure recovery: CETESB's public historical station form for AERIS-selected station 31 after the AERIS/OpenAQ request returned no 2019 records.
- Weather: no-auth Open-Meteo archive API at the municipal centroid. This is a transparent substitute for the published population-weighted ERA5 covariates.

The official DATASUS host can be slow or unavailable. The downloader tries it first and then uses the recorded public mirror. It logs which URL actually supplied the bytes and their SHA-256 hash.

## Run order

Run from this directory with the AERIS environment's Python. `AERIS_REPO` should point to the `agent-first-mcp` checkout and its `.env` must hold `OPENAQ_API_KEY`; this script does not write or copy credentials.

```bash
PYTHON=python
$PYTHON scripts/fetch_sim.py
$PYTHON scripts/ingest_sim.py
$PYTHON scripts/fetch_boundary.py
$PYTHON scripts/fetch_weather.py
$PYTHON scripts/run_aeris_exposure.py
$PYTHON scripts/build_panel.py
$PYTHON scripts/fit_case_crossover.py
```

### Historical recovery run

The current AERIS/OpenAQ boundary run discovers 12 PM2.5 locations inside the
municipality but returns no 2019 measurements. CETESB's public historical form
returns the official daily record for AERIS-selected station 31. This recovery
path retains the AERIS discovery trace and uses the official station series
only for the unavailable historical payload:

```bash
$PYTHON scripts/fetch_cetesb_pm25.py
$PYTHON scripts/build_panel.py \
  --exposure data/derived/cetesb_pm25_daily.csv \
  --output data/derived/analysis_panel_cetesb_recovery.csv \
  --summary data/derived/panel_summary_cetesb_recovery.json
$PYTHON scripts/fit_case_crossover.py \
  --panel data/derived/analysis_panel_cetesb_recovery.csv \
  --output outputs/effect_result_cetesb_recovery.json \
  --exposure-label 'CETESB daily PM2.5 from AERIS-selected station 31; 3-day average, lag 0-2, scaled per 10 ug/m3.'
```

Generated raw data, the local OpenAQ cache, and outputs are ignored by Git. The scripts and manifests are the publishable provenance record. `RESULT.md` is updated only after an actual fit or a terminal, evidenced blocker.

## Completed result

The completed São Paulo 2019 recovery estimates an odds ratio of **1.006** per
10 ug/m3 increase in 3-day PM2.5 (95% CI 0.960--1.054). It uses 333 complete
lagged days, 12,661 cancer deaths, and the exact same-weekday/same-month
case-crossover referent rule. See `RESULT.md` and
`outputs/effect_result_cetesb_recovery.json`.

## Published comparison target

For all cancer mortality, the article reports an odds ratio of 1.04 (95% CI 1.03-1.04) per 10 ug/m3 increase in 3-day average PM2.5 for the full 2000-2019 national analysis. It reports 1.01 (95% CI 1.00-1.02) for 2015-2019. Neither is directly comparable to this one-city, one-year source-substitution result; they are retained as contextual anchors only.

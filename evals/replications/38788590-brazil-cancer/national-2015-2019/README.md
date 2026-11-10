# Brazil national reconstruction, 2015--2019

This directory is the national reconstruction target for PMID 38788590.
It keeps the published study's five-year window, cancer definition, lag 0--2
exposure, and same-weekday/same-month case-crossover design. It reconstructs
exposure from the AERIS/OpenAQ monitor network and never uses the paper's
exposure values.

## Run order

```sh
python3 scripts/fetch_boundary.py
python3 scripts/fetch_sim_national.py --workers 6
python3 scripts/ingest_sim_national.py
python scripts/run_aeris_national_exposure.py
python scripts/fetch_network_weather.py
python3 scripts/fetch_iema_monitor_archives.py
python scripts/ingest_iema_pm25.py
python scripts/fetch_iema_network_weather.py
python3 scripts/build_national_panel.py
python3 scripts/fit_national_case_crossover.py
```

Each step writes a machine-readable manifest beside its output. The OpenAQ
record is retained as the direct AERIS result. The IEMA public-monitor record
is a documented recovery path used when that audit cannot support a fit.

## Scope

The outcome is the daily national count of deaths from the cancer ICD-10 codes
specified by Yu et al. (2015--2019). Exposure is the daily mean across AERIS-
selected public PM2.5 monitors within Brazil. Weather is the corresponding
daily mean across monitor locations from Open-Meteo. This monitor-network
record differs from the paper's population-weighted 0.25-degree PM2.5 and
ERA5 records; the source substitution is part of the evaluation.

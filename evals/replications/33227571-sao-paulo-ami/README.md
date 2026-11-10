# PMID 33227571: São Paulo AMI

This folder reconstructs the paper's daily environmental-cluster analysis for acute myocardial-infarction admissions in 39 São Paulo metropolitan municipalities, 2012-15.

## Run order

```sh
PYTHON=python
$PYTHON scripts/fetch_boundary.py
$PYTHON scripts/fetch_sih.py
$PYTHON scripts/ingest_sih.py
$PYTHON scripts/fetch_weather.py
$PYTHON scripts/run_aeris_exposure.py
$PYTHON scripts/build_panel.py
$PYTHON scripts/fit_clusters.py
$PYTHON scripts/write_run_manifest.py
```

## Inputs

- Daily I21 admissions: public DATASUS SIH/SUS monthly `RDSP` files, filtered by residence in the 39-municipality region and admission date.
- Exposure: AERIS daily boundary exposure records for PM2.5, PM10, and NO2.
- Weather: public Open-Meteo archive at the metropolitan-boundary centroid.
- Geography: public IBGE municipality API and boundary service.

`RESULT.md` is written after the first complete run. All downloaded inputs, transformed panels, model outputs, and checksums remain in this folder.

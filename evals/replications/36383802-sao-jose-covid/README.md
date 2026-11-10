# PMID 36383802: São José dos Campos COVID-19 admissions

This directory reconstructs the public-data components of Nascimento et al.
(2022), *Exposure to air pollution and hospitalization due to COVID-19 in São
José dos Campos, Brazil*.

The paper models daily SIH/SUS admissions with principal ICD-10 diagnosis
`B34.2` from 1 April 2020 through 30 April 2021. Its reported primary effects
are RR 1.061 for a 10 ug/m3 increase in ozone at lag 2 and RR 1.125 for a
10 ug/m3 increase in NO2 at lag 3. This reconstruction obtains admissions
from the public monthly SIH/SUS RD files, estimates exposure through AERIS,
and uses Open-Meteo for daily temperature and relative humidity.

## Run order

```bash
python scripts/fetch_sih.py
python scripts/ingest_sih.py
PYTHONPATH=. \
  python scripts/run_aeris_tools.py
python scripts/fetch_weather.py
python scripts/build_panel.py
python scripts/fit_reproduction.py
```

Each script writes inputs, outputs, and a manifest under this directory. The
older exploratory run remains at `reproduction-eval/runs/36383802-sao-jose-covid`.

## Public fallback used in the completed run

The official SIH/SUS source remains the preferred outcome. Its FTP transfer
did not deliver a monthly RD file during this run. `scripts/ingest_sivep_fallback.py`
therefore derives a daily COVID hospital-admission series from a cited public
SIVEP-Gripe archive. It covers public and private severe-respiratory admissions
and has more admissions than the paper's SIH/SUS series. The resulting model is
a bounded source-substitution analysis and is kept outside the strict
effect-calibration set.

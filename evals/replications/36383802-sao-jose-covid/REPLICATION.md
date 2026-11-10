# Reproduction Record

## Study

- PMID: 36383802
- DOI: 10.1590/1414-431x2021e12273
- Location: São José dos Campos, São Paulo, Brazil
- Original outcome: daily SIH/SUS B34.2 admissions, 1 April 2020 to 30 April 2021

## Inputs

- AERIS: OpenAQ v3 daily retrieval with historical S3 recovery.
- Weather: Open-Meteo municipal-centroid daily mean temperature and relative humidity.
- Outcome fallback: public SIVEP-Gripe hospital archive published by CADDE-CENTRE, filtered to city residents admitted with COVID-19.

## Fit

The fitted negative-binomial model uses ozone at lag 2, NO2 at lag 3, PM10 at
lag 0, temperature, relative humidity, weekday indicators, and linear calendar
day. It contains 89 complete days from the AERIS record.

The model result is `outputs/effect_results_sivep_fallback.json`. The original
SIH/SUS outcome remains pending a successful public RD-file transfer. The
SIVEP-Gripe outcome changes the analytic population, so its effects remain
outside the strict published-effect calibration set.

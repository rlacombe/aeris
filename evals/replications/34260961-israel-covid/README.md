# PMID 34260961: Israel COVID-19 municipal study

This directory is an independent AERIS reconstruction attempt for Levi and
Barnett-Itzhaki (2021), *Effects of chronic exposure to ambient air pollutants,
demographic, and socioeconomic factors on COVID-19 morbidity: The Israeli case
study* (doi: `10.1016/j.envres.2021.111673`).

## Original target

The paper regressed log COVID-19 case rates in Israeli municipalities on one
2016-2019 pollutant at a time and population density, population, matriculation
eligibility, and socioeconomic cluster. Its reported standardized PM2.5
coefficient at the July 24, 2020 peak was 0.403 (`p = 0.001`). The original
exposure was a 3 km Israeli Ministry of Environmental Protection CHIMERE and
monitoring hybrid model, not OpenAQ.

## Public inputs and commands

```bash
python build_public_inputs.py
python run_aeris_tools.py
python fit_public_model.py
python audit_historical_pm25_catalog.py pm25
python audit_historical_pm25_catalog.py pm10
python audit_historical_pm25_catalog.py no2
python run_aeris_no2_2018.py
python fit_no2_2018_public_model.py
```

`build_public_inputs.py` downloads and hashes the cited 2019 Israel Central
Bureau of Statistics locality workbook, converts its published Israel TM centre
points to WGS84, and pages the Israel Ministry of Health CKAN datastore. It
writes the four peak-date outcome panel and the AERIS static cohort. It does not
load any original pollutant data.

The outcome resource is the Ministry of Health COVID-19 city table, resource ID
`8a21d39d-91e3-40db-aca1-f73f7ab1df69`, retrieved through
`https://data.gov.il/api/3/action/datastore_search`. The original direct CSV
download is browser-protected, but this official datastore API is public and
returns the same source table.

`run_aeris_tools.py` calls the AERIS agent contract with `load_cohort`,
`plan_exposure`, `estimate_exposure`, `export_results`, and
`get_decision_log`. It splits the four-year period into four annual cohorts so
that the AERIS public-S3 archive fallback remains within its 366-day safety
bound. `fit_public_model.py` joins the July 24, 2020 outcome table to the
reconstructed study-period panel and refuses to estimate a coefficient if the
exposure has no municipal variation.

`audit_historical_pm25_catalog.py` separately audits every current Israeli
OpenAQ location carrying a requested parameter. It lists S3 objects, without
downloading measurements. `run_aeris_no2_2018.py` then runs the same AERIS
tool contract for 2018 NO2. It supports a closest public measured-pollutant
sensitivity model because 2018 is the only near-complete shared year in the
available NO2 archive. `fit_no2_2018_public_model.py` fits that model with
July 24, 2020 municipal case rates and standardized log population.

## Result: target PM2.5 effect unavailable; NO2 sensitivity model fitted

Checked on 2026-08-15, AERIS found one historical Israeli PM2.5 location:
OpenAQ location `1285358` (`SPARTAN - Weizmann Institute`), sensor `6566251`.
The annual runs combine OpenAQ v3 daily data with the public S3 archive:

| Year | Municipalities with an assigned value | Daily values at the sole station | Mean PM2.5 (ug/m3) |
| --- | ---: | ---: | ---: |
| 2016 | 38 | 314 | 15.016 |
| 2017 | 38 | 239 | 14.050 |
| 2018 | 0 | 0 | -- |
| 2019 | 38 | 50 | 13.019 |

Every covered municipality is assigned this same sole-station annual value.
The study-period panel consequently has one station assignment, one exposure
value, and zero municipal exposure range. `public_model_attempt.json` records
the resulting non-identifiability: an unadjusted or adjusted PM2.5 coefficient
would be collinear with the intercept, so no effect is estimated or compared
with the paper's standardized PM2.5 coefficient (0.403).

The catalog audit confirms the PM2.5 limitation: 14 current Israeli PM2.5
locations were checked against S3, and only location `1285358` had any
2016-2019 objects. The three current PM10 locations had zero S3 objects for
the same window. `openaq_pm25_catalog_audit.csv` and
`openaq_pm10_catalog_audit.csv` retain the location-level evidence.

The same audit found S3 objects for all 119 current Israeli NO2 locations in
2017-2019, with no 2016 values. AERIS assigned 2018 NO2 to 189 of 194
municipalities, using 66 stations. The prespecified minimum of 180 daily
values retained 171 municipalities. The standardized model of July 24, 2020
log case rate on NO2 and log population estimated a NO2 coefficient of
`-0.0016` (95% CI `-0.1487` to `0.1455`, `p=0.983`; model R2 `0.101`).

The public measured-pollutant sensitivity analysis uses NO2 from 2018. The
paper reports NOx averaged across 2016-2019, adjusted for density,
matriculation eligibility, and socioeconomic cluster. The saved NO2 result
therefore remains outside the paper's PM2.5/NOx effect comparison.

This is a coverage result for the AERIS/OpenAQ substitution, not a failure to
recover the outcome data. The original paper's gridded IMoEP exposure product
would remove this limitation, but is deliberately not substituted here because
the benchmark tests AERIS's independently reconstructed OpenAQ exposure.

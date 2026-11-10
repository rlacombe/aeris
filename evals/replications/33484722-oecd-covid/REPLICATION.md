# Reproduction Status

## Target

PMID 33484722 reports four cross-country linear regressions of log COVID-19
case and death rates at 60 and 80 days after first reported case. Its original
exposure is World Bank population-weighted 2017 PM2.5. This run reconstructs
the 2017 exposure through the AERIS/OpenAQ country-boundary monitor record.

## Public inputs

- WHO country outcome series: 36 study countries x two event times in
  `public-inputs/country_outcomes_event_days.csv`.
- World Bank covariates and raw API responses:
  `public-inputs/source_manifest.json`.
- Country boundaries: pinned Natural Earth v5.1.2 Admin 0 GeoJSON,
  SHA-256 `6866c877d39cba9c357620878839b336d569f8c662d3cfab4cb1dbe2d39c977f`.

## Completed AERIS retrieval

The AERIS `estimate_boundary_exposure` tool ran for each study country against
a pinned country polygon, daily aggregation, and the 2017 window. The run used
a 20-station discovery cap and a ten-request-per-minute OpenAQ limit. Its tool
calls and decision logs are in `aeris_tool_trace.json`.

| Retrieval outcome | Countries |
| --- | ---: |
| `PASS` at 75% annual coverage | 7 |
| Mean PM2.5 available, 65-75% coverage | 4 |
| Mean PM2.5 available, below 65% coverage | 9 |
| `NO_STATIONS` | 14 |
| `NO_OBSERVATIONS` | 4 |
| Retrieval error | 2 |

`aeris_pm25_2017_country_summary.csv` contains all 36 outcomes. The eleven
records at or above 65% coverage form the closest complete public-data model.
They draw on OpenAQ v3 and, for ten countries, the OpenAQ historical S3
archive.

## Fitted models

`fit_reproduction.py` fits the paper's day-60 and day-80 case and death-rate
outcomes. It attempts the published covariate specification and a predefined
complete public-data specification. The complete model uses PM2.5, age 65+,
density, and GDP per capita. The model results are in
`reproduction_model_results.csv` and `reproduction_model_results.json`.

The 75% analysis has seven countries. The 65% coverage sensitivity has eleven
and supplies the primary fitted comparison. `RESULT.md` gives the four effect
estimates alongside the paper's published PM2.5 coefficients.

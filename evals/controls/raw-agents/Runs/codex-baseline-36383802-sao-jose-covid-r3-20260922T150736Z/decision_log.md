# Decision log

## Reconstructed study contract

- Outcome: daily count of SUS hospital admissions among residents of São José dos Campos, SP (IBGE municipality 354990), principal ICD-10 diagnosis `B342`, by admission date (`DT_INTER`).
- Period: 2020-04-01 through 2021-04-30 (395 calendar days).
- Unit: municipality-day.
- Pollutants: O3, NO2, and PM10, each at lags 0 through 7 days.
- Published covariates: temperature, relative humidity, day of week, and calendar day.
- Published model: negative-binomial regression; coefficients transformed as `exp(beta * 10)` to RR for a 10 ug/m3 increment. The article highlights O3 lag 2 and NO2 lag 3 but reports every pollutant-lag comparison.

## Health-data decision and sanitization

The direct DATASUS FTP request for the April 2020 RDSP file timed out. The fallback is a public SIH-RD re-release that identifies the official DATASUS origin and exposes monthly Parquet partitions. This is a source substitution, not an outcome substitution.

Before filtering or analysis, `reanalyze.py` reads only `MUNIC_RES`, `DIAG_PRINC`, and `DT_INTER`. Its audit is in `sanitization_audit.json`, listing every retained and dropped source column for each month. The retained values yield 1,873 eligible records, precisely the article's stated total. No author-released data table, pollution field, fitted value, or analysis code was used.

## Exposure and model decision

The independent Open-Meteo air-quality response was retrieved for the requested coordinates, dates, and hourly O3/NO2/PM10 fields, plus a seven-day lead-in for lags. It contains null pollutant values at every hour, thus at every one of 402 daily aggregates. Weather covariates were available from the separate archive endpoint. Because all three pollutant series have zero usable observations, no lagged exposure panel exists and no negative-binomial model can execute. The script deliberately writes an empty model-output table rather than changing source, pollutant, period, or coverage standard after inspecting data.

The results therefore have status `completed_blocker`, not a null effect estimate.

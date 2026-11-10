# Blocker ledger

| ID | Status | Evidence | Consequence |
|---|---|---|---|
| B1 | terminal scientific/data blocker | `raw/openmeteo_hourly.json` was HTTP 200 and has 402 dates, but ozone, nitrogen_dioxide, and pm10 are null for all hourly records. `exposure_daily.csv` shows 402 missing values for each pollutant. | The specified lagged negative-binomial exposure comparison has no rows with exposure and cannot be fitted. |
| T1 | recovered transport issue | Direct `ftp.datasus.gov.br` RDSP2004 request timed out after 30 seconds; log header file is `logs/ftp_http_headers.txt`. | Substituted a public SIH-RD re-release of the same official health-record construct; outcome definition was unchanged. |

No outcome, geography, temporal, covariate, or model substitution was made to overcome B1. No effect estimate is reported.

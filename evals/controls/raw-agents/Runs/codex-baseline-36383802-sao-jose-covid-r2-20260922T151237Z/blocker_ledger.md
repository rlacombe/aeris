# Blocker ledger

| ID | Status | Evidence | Consequence |
| --- | --- | --- | --- |
| B1 | terminal transport failure | `ftp.datasus.gov.br` HTTPS and FTP requests timed out; request context is recorded in `request_log.csv` and execution transcript | Original daily SIH-SUS B34.2 outcome could not be obtained. SIVEP-Gripe was disclosed as a non-identical fallback. |
| B2 | completed data-coverage blocker | `raw/openmeteo_air_quality.json`, `exposure_daily.csv`, and `analysis_panel.csv` show null O3, NO2, and PM10 on all 395 dates | The reconstructed panel does not support a principal comparison. No regression estimate is reported. |

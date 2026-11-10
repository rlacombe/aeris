# Blocker ledger

| ID | Severity | Evidence | Consequence | Disposition |
|---|---|---|---|---|
| B1 | Principal-model blocker | The Civil Protection regional CSV starts 2020-02-24; study lockdown begins 2020-02-22. `analysis_panel.csv` has `lockdown=1` in every row. | Lockdown and intercept are collinear; the published adjusted model cannot be reconstructed. | No imputation or change of lockdown definition. |
| B2 | Inferential blocker | `analysis_panel.csv` has exactly 2 regions/GEE groups. `logs/reanalysis_stderr.log` records robust-covariance warnings. | Cluster-robust GEE confidence intervals cannot be treated as reliable. | Diagnostic output retained but no effect reported. |
| B3 | Exposure-coverage limitation | `exposure_region_day_long.csv` has 2,331 observed dates per pollutant-region in a 2,696-day target window. | LTAP differs from a complete 8-year calendar-day average. | Mean of observed days used and disclosed; no gap filling. |

No transport endpoint reached a terminal failure. The formerly published EEA export URL returned HTTP 404 because the service was discontinued; the current EEA download API was used as the documented replacement.

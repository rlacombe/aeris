# Blocker ledger

| ID | Severity | Evidence | Consequence | Disposition |
|---|---|---|---|---|
| B1 | Blocking | `raw/attempt_e620b88e91.headers` is empty after a 20-second HTTP connection timeout to the official SIH file; `raw/datasus_headers.txt` is empty after HTTPS timeout; `raw/datasus_portal_query.headers` records HTTP 500 and its body is empty. | Daily AMI admissions cannot be reconstructed. | No model fitted. |
| B2 | Blocking | `raw/openmeteo_2012.json` says 2012 is outside the allowed range; `raw/openmeteo_2013.json`, `openmeteo_2014.json`, and `openmeteo_2015.json` contain zero non-null values for each requested exposure/covariate. | No independent pollution or meteorology exposure can be assigned. | No clustering or model fitted. |
| B3 | Non-blocking but material | Supplied reading copy is citation/abstract metadata only; its reported cluster days total 1,092 despite the stated 2012--2015 period. | Exact cluster algorithm and comparison model cannot be locked. | Logged; no assumptions made. |
| B4 | Non-blocking | The `record_reanalysis_fidelity` executable/API is not present in the supplied environment (`command -v` returned no path). | Automated fidelity capture could not be invoked. | A transparent equivalent record is saved as `fidelity_record.json`. |

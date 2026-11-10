# Blocker ledger

| ID | Blocker | Evidence | Consequence |
|---|---|---|---|
| B1 | CDC WONDER county outcome extraction did not yield data | `cdc_request_form.html`, `cdc_outcome_response.html` | No age-65+ county ischemic-stroke outcome table. |
| B2 | Independent AQS monitor exposure is incomplete | `exposure_table.csv`; only 2016 and 2020 archives completed | Cannot assign a 2016--2020 annual exposure to all 3,142 eligible counties. |
| B3 | Locked covariates absent | Article methods and empty `analysis_panel.csv` | Adjusted principal OLS model cannot be fit. |

This is a scientific/data-coverage blocker, not an infrastructure retry condition.

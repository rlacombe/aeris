# Blocker ledger

| ID | Status | Blocker | Evidence | Consequence |
| --- | --- | --- | --- | --- |
| B1 | terminal | No independently sourced, daily PM2.5 municipality exposure table spanning all 5,570 Brazilian municipalities from 2000-01-01 through 2019-12-31 was retrieved. | `logs/nasa_merra_head.txt` records HTTP 404 for the evaluated independent candidate; `model_output.json` and `source_manifest.json` preserve the decision. The article's own underlying global PM product is prohibited. | No valid case/control exposure assignment; conditional logistic model was not constructed or fit. |
| B2 | non-decisive | Direct legacy DATASUS FTP request for `DO2000.dbc` timed out in this environment. | `logs/datasus_2000_head.txt`. The Ministry documents alternative public SIM routes, so this is not asserted as an outcome-data impossibility. | Outcome extraction was not pursued after B1 already prevented a valid model. |

No model failure occurred. The model was intentionally not run because its required input panel was absent.

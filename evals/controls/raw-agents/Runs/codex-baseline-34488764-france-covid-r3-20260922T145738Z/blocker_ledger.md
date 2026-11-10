# Blocker ledger

| ID | Blocker | Evidence | Consequence | Resolution |
|---|---|---|---|---|
| B1 | Exact independent temperature exposure, 2001--2012 | Article specifies WorldClim temperature for 2001--2012 and says it was used in every regression; no completed independent department-level construct is in the panel. | Locked principal NB model cannot be executed. | Do not omit/replace temperature silently; result is `completed_blocker`. |
| B2 | No PM2.5 grid cell inside Hauts-de-Seine | `exposure_table.csv` has missing `pm25_1999_2016` for code 92 after polygonal extraction from the 0.1-degree independent grid. | Exposure-complete sample is 95/96 departments. | No centroid or nearest-cell assignment; preserve missingness. |

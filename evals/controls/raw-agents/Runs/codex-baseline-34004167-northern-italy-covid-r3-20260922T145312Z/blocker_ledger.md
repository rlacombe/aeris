# Blocker ledger

| ID | Severity | Evidence | Consequence | Disposition |
| --- | --- | --- | --- | --- |
| B1 | Blocking | `analysis_panel.csv` begins 2020-02-24; `fidelity_record.json` lists 2020-02-21 through 2020-02-23 missing. | 172/178 target region-days; no observations precede LOCK=1. | Do not relax the period or omit LOCK. |
| B2 | Blocking | `analysis_panel.csv` has `lock=1` in all 172 rows. | The published LOCK-adjusted model has a non-estimable covariate. | No GEE fit. |
| B3 | Blocking | `exposure_table.csv` is header-only; ARPA Lombardia file is annual; ARPAV page says CSV is emailed; OpenAQ response is 401. | No independent region-day STAP or 2013-2020 LTAP for all five pollutants. | Do not substitute author-derived EEA fields or invent exposure values. |
| B4 | Nonblocking provenance limitation | Current GitHub outcome file is a later repository snapshot. | It may differ from values known as of 19 May 2020. | Date-filtered records retained; no numerical comparison reported. |

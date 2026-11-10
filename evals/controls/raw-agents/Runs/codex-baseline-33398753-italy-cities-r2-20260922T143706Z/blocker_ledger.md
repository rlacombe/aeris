# Blocker ledger

| Status | Blocker / limitation | Evidence | Effect on result |
|---|---|---|---|
| Open limitation | The published 55-city random sample is not identifiable. | Article supplies N=55 but no city roster, random seed, or row data. | Full 107-province/capital frame used as disclosed geographic substitution. |
| Open limitation | Official outcome data are provincial, not municipal/capital-city. | Civil Protection `dati-province` source and source manifest. | Outcome-geography substitution. |
| Open limitation | City density is not reproducibly available from the article. | Article reports city density but does not give values or city roster. | Istat NUTS3 population / GISCO NUTS3 area substituted. |
| Open limitation | Complete log–log panel is small. | `analysis_panel.csv`, `exposure_table.csv`. 107 eligible frame; 64 nearest-station assignments; 35 positive PM10 counts; 18 complete model records. | Estimates are fitted but imprecise and not a direct reproduction. |
| Resolved transport issue | Legacy EEA E1a per-station Blob link returned 404. | `logs/pm10_IT1099A.parquet.http.json`. | Recovered via the current EEA Download Service’s identical-filter URL list; no scientific target changed. |


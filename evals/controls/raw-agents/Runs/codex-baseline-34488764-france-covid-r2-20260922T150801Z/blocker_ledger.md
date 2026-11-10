# Blocker ledger

| ID | Status | Evidence | Consequence |
|---|---|---|---|
| B1 | terminal scientific/data blocker | `exposure_eea_pm25_2016_stations.csv` has 2 rows after fixed public EEA query; `analysis_panel.csv` has PM2.5 missing for all 864 department-date rows. | No valid department-level PM2.5 quartiles or continuous exposure; do not fit. |
| B2 | terminal scientific/data blocker | Article requires a 1999--2016 department mean; independent EEA source returned annual 2016 monitor statistics only. | Cannot substitute a one-year, two-location monitor measure for the published long-term department exposure. |
| B3 | terminal supporting-data blocker | Article names health-service, demographic, socioeconomic, temperature, diabetes, and population inputs, but no author-designated full table URL was supplied/retrieved. `sanitization.json` records non-use. | Adjusted published model and explicit count offset cannot be reconstructed. |
| B4 | documented specification ambiguity | Article calls the result a mortality rate ratio but does not state the negative-binomial offset. | No unannounced offset choice was made. |

Transport status: both attempted public requests succeeded on their first attempt; see `request_log.json`. No retry or human intervention occurred.

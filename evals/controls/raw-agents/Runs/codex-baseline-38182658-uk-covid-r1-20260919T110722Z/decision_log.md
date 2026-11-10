# Independent reanalysis decision log

- Study identified from supplied materials: Hossain et al., *Scientific Reports* (PMCID PMC10770173), UK first-wave COVID-19 case fatality.
- Published target: four UK countries, daily 26 March–15 September 2020; outcome is iCFR, deaths retrospectively assigned to confirmation date; selected model contains temperature, sunlight, PM2.5, exposure-day RH, weekday and country random effects.
- Health input: official UKHSA archived `nation_newCasesByPublishDate` and `nation_newDeaths28DaysByPublishDate`, restricted exactly to the four countries and date range. This is a retrieval from the public successor archive, not author data.
- Exposure: country-centroid Open-Meteo/CAMS PM2.5 hourly series, aggregated to calendar-day means. It is independent of the article authors and DEFRA data. Country-centroid assignment is a geographic/exposure substitution, explicitly recorded in `result.json`.
- Covariates: Open-Meteo archive temperature, RH and sunshine duration, likewise country-centroid daily aggregates.
- Back-projection blocker resolved by disclosed substitute: the article reports only the gamma delay mean (7.92 days), not the shape/scale required to reproduce `backprojNP`; deaths are shifted eight days backward, not represented as the article's iCFR.
- Model: 0–10-day rolling means for PM2.5/temperature, 0–13-day sunlight mean, RH at 10-day lag; binomial logit with country fixed effects and weekday. This is not an exact DLNM/GLMM. The PM2.5 estimate is therefore an independently reconstructed, adjusted lag-window association—not a replication claim.
- Coverage rule: observations must have all lagged fields, positive cases, and 0 <= shifted deaths <= cases. The supplement's pooled 2.5th–97.5th percentile trimming is applied to the three main predictors. Counts are reported in `result.json`.
- Retrieval policy: all successful Open-Meteo requests and byte counts are in `source_manifest.json`. The legacy `api.coronavirus.data.gov.uk` DNS failure is preserved in `http_outcome_headers.txt`/terminal transcript; the successor archive was then used, which is a source substitution rather than a retry.

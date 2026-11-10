# Reanalysis decision log

The article (PMID 38182658) selected a four-country UK panel from 26 March through 15 September 2020. Its outcome is instantaneous CFR: back-projected COVID-19 deaths divided by confirmed cases. The selected model includes distributed-lag temperature, sunlight duration and PM2.5, linear humidity at exposure, weekday, and a country random effect. Figure 2C declares the PM2.5 reference of 10 ug/m3 and reports 19 versus 10 ug/m3 at one day after symptom onset.

No author exposure values, exposure tables, fitted values, or analysis code were used. The health source was sanitized to `date`, `location_key`, `new_confirmed`, and `new_deceased` before analysis; the complete retained/dropped list is in `sanitization_columns.json`.

Independent exposure is Open-Meteo's CAMS PM2.5 reanalysis at each constituent nation's centroid. ERA5 temperature, relative humidity and shortwave radiation were retrieved from Open-Meteo at the same centroids. Shortwave radiation is a disclosed replacement for published sunshine duration, so its units and interpretation differ.

The public outcome source covers all four nations/dates. The original `backprojNP` gamma back-projection was not available in the execution environment. Deaths were therefore shifted eight days (the published 7.92-day mean rounded to days) to their presumed confirmation date. The original DLNM mixed model could likewise not be executed without its R dependencies; the executable analysis fits a clearly labeled lag-3 linear binomial-logit approximation, with country and weekday fixed effects and HC1 covariance. Lag 3 is the nearest integer to exposure one day after onset given the paper's 4.03-day onset-to-confirmation delay. This is an independent approximate reanalysis, not a replication of the paper's DLNM estimate.

Rows where shifted deaths exceeded cases are excluded because a binomial outcome is invalid; the exact records and counts are saved. The PM comparison is exactly 19 versus 10 ug/m3, derived as `exp(beta_PM25 * 9)`; the native coefficient and confidence interval are in `model_output.json`.

The supplied JSON schema has `additionalProperties: false` but does not declare the separately required `fidelity_record` property. `result.json` includes it because the task explicitly requires that field. This is the only intentional incompatibility with the supplied schema.

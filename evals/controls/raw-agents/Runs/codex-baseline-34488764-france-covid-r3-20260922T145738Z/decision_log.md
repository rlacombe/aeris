# Decision log

- Locked target inferred from PMID 34488764: cumulative COVID-19 hospital deaths by metropolitan French department on nine dates in 2020; long-term PM2.5 quartiles (Q2, Q3, Q4 versus Q1); negative-binomial rate-ratio model with log population offset, long-term temperature, and the listed health-service, demographic, socioeconomic, urbanicity, density, and diabetes covariates.
- Outcome was independently retrieved from the French Ministry of Health departmental hospital series. `sexe == 0` is the total-sex record; `dc` is cumulative hospital deaths.
- The author-designated supplementary Table 1 was parsed only after a declared sanitization step. It contains non-exposure covariates. The retained and dropped fields are in `sanitization.json`; no author PM2.5, temperature, outcome, fitted values, or derived analyses were read into modelling.
- PM2.5 was independently constructed from ACAG V6.GL.03 annual 0.1-degree public grids. For each department, pixels intersecting the official boundary were averaged within each year and then equally averaged over 1999--2016. This is an explicitly disclosed exposure-product/resolution substitution from the article's V4/claimed 1-km release.
- No principal estimate was fit. The article requires temperature in every published regression. An exact independently aggregated 2001--2012 department temperature field was not completed in this run, so omitting it would silently change the locked model.
- Hauts-de-Seine has no in-polygon cell in the coarse independent PM2.5 grid. It is retained as missing in the exposure and analysis tables, not imputed or assigned a nearby value.

## Transport notes

- The original SEDAC map endpoint did not return headers within 30 seconds. Per policy, it was treated as an infrastructure/transport failure and an alternate public release (ACAG's public S3 bucket) was used for the same PM2.5 construct.
- All downloaded PM2.5, outcome, and boundary objects used in the run are checksum-listed in `source_manifest.json`.

# Decision log — independent reanalysis

## Target identified from the supplied article

The article's principal all-county comparison is ordinary multivariable linear regression of county ischemic-stroke mortality among adults aged 65 years or older (deaths per 100,000) on annual county PM2.5 (µg/m³), United States counties/county equivalents, described as 2016–2020. Its reported PM2.5 coefficient is 1.89 deaths per 100,000 per 1 µg/m³. The specified covariates are CAD, hypertension, hyperlipidemia, diabetes, obesity, smoking, median household income, Gini index, poverty, uninsured percentage, and park access.

## Public-input decisions

* I retrieved CDC's public Atlas CSV for the available 2018–2020 period and EPA AQS annual monitor-concentration files for 2018, 2019, and 2020. No author exposure table, code, or derived dataset was used.
* The CDC extract contains 3,226 county records but its available outcome is **all stroke**, age-adjusted, spatially smoothed, 3-year average rate for ages 35+, not ischemic stroke among ages 65+.
* Independent PM2.5 was defined before inspection as the arithmetic mean for EPA AQS parameter 88101, averaged across valid monitor records within county-year and then across 2018–2020. This is direct monitoring, not the article's undisclosed county exposure product.
* EPA AQS does not provide a monitor exposure for most counties. The observed coverage statistics are emitted by `reanalysis.py` in `coverage_summary.json`.

## Stop decision

No principal model was fit. Fitting would require (1) changing the outcome definition and study period, (2) accepting a nonrepresentative monitored-county subset for a study whose target is all U.S. counties, and (3) omitting every published adjustment covariate. Those are material scientific substitutions, not permissible retries. The public outcome and exposure extracts, the attempted panel, and executable code are retained for verification.

## Retrieval / retry record

All five static public downloads returned HTTP 200 on their first request; no retries, query changes, or transport substitutions were made. The Atlas application's undocumented API was not used as a health-data source; the documented public CSV export was used instead.

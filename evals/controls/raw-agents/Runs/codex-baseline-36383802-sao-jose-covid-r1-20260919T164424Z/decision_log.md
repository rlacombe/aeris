# Independent reanalysis decision log

Study: PMID 36383802, “Sao Jose dos Campos COVID admissions.”

## Frozen target

The article's principal time-series analysis is daily hospital admissions for residents of São José dos Campos (IBGE 354990), 1 April 2020–30 April 2021, from SIH/SUS AIH-reduced records with principal diagnosis B34.2. It fits negative-binomial count regressions for O3, NO2, and PM10 at lags 0–7, adjusting for temperature, relative humidity, day of week, and calendar day. Reported effect scale is RR per 10 µg/m³. The reported largest associations are O3 lag 2 and NO2 lag 3.

## Independent inputs and frozen analysis plan

The outcome source is the official DATASUS SIH/SUS monthly RDSP DBC microdata, filtered to municipality of residence 354990 and B34.2 and grouped by admission date. The required files are RDSP2004–RDSP2012 and RDSP2101–RDSP2104. This is the article's named public system, not an author-derived file.

Exposure uses Open-Meteo's public air-quality endpoint (CAMS gridded fields) at -23.1791, -45.8872. O3 is assigned as daily maximum; NO2 and PM10 as daily arithmetic means of local-time hourly values. Meteorology comes from Open-Meteo archive (ERA5-Land), using daily maximum 2-m temperature and mean relative humidity. These are disclosed exposure/covariate substitutions for the article's CETESB station data. Had a panel been available, it would retain all 395 calendar days, create lag 0–7 pollutant values, and fit negative-binomial models with the published covariates and calendar controls; no coverage relaxation or outcome substitution was authorized.

## Coverage decision and blocker

The run made repeated identical connection attempts to the first official outcome object (the connection failed before an HTTP response each time); the final durable attempt is recorded in `retrieval_log.json`. The source could not be connected to, so daily outcome counts cannot be constructed. In addition, the requested Open-Meteo air-quality response contains its 395 expected dates but null values for all three pollutants, so it supplies 0/395 complete exposure days. This valid empty result is data evidence, not a transport failure. No model was fit and `analysis_panel.csv` deliberately contains only its header. `model_output.txt` records both blockers. The exposure table retains the returned nulls rather than imputing them.

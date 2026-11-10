# Reanalysis decision log

Study: PMID 33398753 / PMC7781409, *Italian provincial capitals COVID-19*.

## Locked reconstruction target

- Outcome: cumulative confirmed COVID-19 cases on 17 March 2020, 7 April 2020, and 27 April 2020. The article calls the first of these model 1; it is primary here.
- Pollutant/exposure: count of 2018 days with daily maximum PM10 >50 µg/m³. The article broadly describes PM10-or-ozone exceedance days, while its Table 6 specifically labels PM10; this reconstruction uses the Table-6 PM10 definition.
- Model: OLS of log(cases) on log(PM10 exceedance days) and log(population density), with intercept. The native PM10 coefficient is an elasticity. The reported outcome ratio is `exp(beta * log(2))`, the fitted ratio for doubling exceedance days.
- Published geography: an unspecified random sample of 55 Italian provincial-capital cities. The article does not give the city list, randomization seed, or row-level data.

## Data and assignment decisions

1. Used the Italian Civil Protection public province archive for cumulative cases. It is the closest official public construct, but is a **province-level** series, not a city series.
2. Used EEA verified daily PM10 measurement files, independently of the authors. A station was assigned as the nearest EEA PM10 station to the Civil Protection province coordinate. Daily maximum readings were aggregated, then days >50 µg/m³ counted.
3. Used Istat 2019 province (NUTS3) population and GISCO NUTS3 polygon area to construct population/km². This is province density, not the article's city density.
4. The implemented analytical frame begins with all 107 eligible province/capital records, rather than inventing the unpublished 55-city selection. Only records with an assigned PM10 station, positive exceedance count, all three case observations, Istat population, and GISCO area enter log–log OLS.
5. Exposure was not imputed. Zero PM10-exceedance records cannot enter a log(exceedance-days) specification; neither can records with no matching station or covariate.

## Transport recovery

The station map's old E1a Blob URLs returned HTTP 404 (one example is retained in `logs/pm10_IT1099A.parquet.http.json`). Per the retry policy, this was not blindly retried. The replacement was the EEA's public Download Service API with exactly: country=IT, pollutant=PM10, aggregation=daily, dataset=E1a/verified, 2018-01-01 through 2018-12-31. Its response is retained as `raw/eea_pm10_2018_urls.csv`.

## Author-table sanitization

No author-designated analytical table was used. Consequently, no author-table columns were inspected or modeled and no sanitization input was needed. `sanitization_record.json` explicitly records the empty retained/dropped sets.


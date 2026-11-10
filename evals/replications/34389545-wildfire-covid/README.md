# Zhou et al. wildfire and COVID-19 replication

This folder reconstructs the PM2.5 component of Zhou et al. (2021), PMID
34389545, DOI `10.1126/sciadv.abi8789`, using AERIS public monitoring data.

## Study target

The paper studied daily PM2.5 and COVID-19 cases and deaths in 92 wildfire-
affected counties in California, Oregon, and Washington from 15 March through
16 December 2020. It reported a 28-day cumulative 10 ug/m3 PM2.5 increase of
11.7% for cases and 8.4% for deaths.

## Independent reconstruction

`run_reconstruction.py` receives county boundaries, population, and daily
COVID-19 outcomes from the authors' public package. It excludes all author
exposure, smoke, wildfire, weather, mobility, and merged-analysis files.

AERIS loads the western-US OpenAQ PM2.5 monitor catalogue, assigns each county
centroid its nearest historical monitor within 100 km, retrieves daily records
through the OpenAQ API. `AERIS_USE_S3_FALLBACK=true` enables the public OpenAQ
S3 archive for missing API dates. The first runnable panel uses monitors
assigned to the 24 highest-population counties before exposure retrieval.
Counties with at least 75% observed daily PM2.5 are eligible. Set
`AERIS_MAX_MONITORS=0` to retrieve the full panel. The analysis fits county
fixed effects, a six-degree calendar-time spline, a population offset, and the
mean PM2.5 exposure across lags 0--28.

The approximation does not reproduce the paper's Bayesian zero-inflated
negative-binomial model or its weather and mobility adjustments. `RESULT.md`
states the observed coverage and fitted comparison.

Run:

```sh
./run.sh
```

## Files

- `source_manifest.json`: exact public inputs, hashes, exposure assignment, and outputs.
- `outputs/county_day_panel.csv`: reconstructed non-author exposure panel.
- `outputs/model_result.json`: case and death estimates when coverage permits.
- `RESULT.md`: concise result and comparison.

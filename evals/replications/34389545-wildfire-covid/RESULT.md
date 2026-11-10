# Result: exposure panel completed; model not fit

The first bounded AERIS reconstruction completed on 2026-08-15. It used the
authors' public county identifiers, boundaries, population, and daily COVID-19
outcomes. It did not use author pollution, smoke, wildfire, weather, mobility,
or merged-analysis data.

## Exposure reconstruction

- The western-US OpenAQ catalogue yielded 116 distinct historical PM2.5
  monitors for 132 of 133 candidate county centroids within 100 km.
- The bounded first panel selected 24 monitors from the highest-population
  counties before any exposure retrieval. Those monitors served 26 counties.
- The API returned 4,576 observed county-days across 17 counties with at least
  75% daily PM2.5 coverage during the 277-day study window.
- Median assigned monitor distance was 11.4 km; the maximum was 34.3 km.
- Four selected counties had no API PM2.5 records: Los Angeles, San Joaquin,
  Multnomah, and Pierce.

The complete exposure panel, county coverage, monitor assignments, and
retrieval audit are in `outputs/`.

## Model status

The planned Poisson county-day approximation did not produce an effect estimate.
Its first fit had a singular design matrix caused by a duplicated intercept in
the time-spline design. No alternative model was run. The next bounded step is
to correct that matrix construction and refit cases and deaths on the recorded
17-county panel. This run does not provide a comparison with the paper's
Bayesian zero-inflated negative-binomial distributed-lag estimates.

# Result: Northern Italy COVID-19

Study: PMID 34004167, *Effects of short- and long-term exposure to atmospheric
pollution on COVID-19 risk and fatality: analysis of the first epidemic wave in
northern Italy*.

## PM2.5

The public Italian Civil Protection regional outcome series is available for
Lombardia and Veneto. AERIS queried OpenAQ V3 and its public S3 archive for
daily PM2.5 from 24 February through 19 May 2020.

| Region | Historical PM2.5 record | Result |
| --- | --- | --- |
| Lombardia | 28 OpenAQ locations were identified; their S3 objects contained no PM2.5 rows. | No PM2.5 panel |
| Veneto | No OpenAQ PM2.5 location overlapped the study window. | No PM2.5 panel |

The PM2.5 model was not fit. The failed retrieval evidence remains in
`aeris-openaq-s3/aeris_tool_trace.json` and the May-overlap chunk trace.

## NO2 short-term reconstruction

NO2 is one of the paper's published short-term pollutants. AERIS recovered a
complete 14-day NO2 record for both regions from 6 through 19 May 2020. The
model used daily new cases, daily deaths derived from the official cumulative
death series, a regional intercept, and a Poisson log-link GEE with AR(1)
working correlation.

| Outcome | Published short-term NO2 ratio per µg/m3 | AERIS ratio per µg/m3 | AERIS 95% interval |
| --- | ---: | ---: | --- |
| Incidence | 1.00 | 1.051 | 1.042 to 1.060 |
| Mortality | 1.00 | 0.988 | 0.987 to 0.990 |

The article reports its NO2 ratios rounded to two decimals. Their underlying
effect estimates are unavailable, so this result cannot enter the numerical
effect-calibration analysis. The 14-day public overlap also lacks variation in
the published lockdown indicator and has no independently reconstructed
eight-year NO2 term.

## Files

- `aeris-openaq-s3/aeris_no2_overlap_tool_trace.json`: AERIS tool calls and
  recovered source details.
- `aeris-openaq-s3/aeris_no2_overlap_daily.csv`: regional daily NO2 panel.
- `aeris-openaq-s3/aeris_no2_overlap_stations.csv`: contributing-monitor
  coverage records.
- `aeris-openaq-s3/no2_overlap_panel.csv`: merged exposure and outcome panel.
- `aeris-openaq-s3/no2_overlap_model_results.json`: fitted coefficients and
  intervals.

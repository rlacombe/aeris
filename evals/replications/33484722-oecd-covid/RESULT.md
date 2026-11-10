# Result: PMID 33484722

## Status

Completed closest public-data reconstruction.

The study reported four cross-country regressions of log COVID-19 case and
death rates on long-term PM2.5. AERIS reconstructed 2017 PM2.5 from OpenAQ v3
and the OpenAQ historical S3 archive for all 36 OECD study countries. The
model uses the 11 country records with at least 65% annual network coverage.

## AERIS exposure record

- Pollutant: PM2.5
- Period: 2017-01-01 through 2017-12-31
- Spatial assignment: unweighted mean of contributing monitor means inside a
  pinned Natural Earth country boundary
- Data source: OpenAQ v3 with historical S3 recovery where needed
- Retrieval outcomes: 7 `PASS` at 75% coverage, 4 additional records at
  65-75%, 9 lower-coverage records, 14 `NO_STATIONS`, 4 `NO_OBSERVATIONS`,
  and 2 retrieval errors.
- Model panel: Belgium, Canada, Chile, Czech Republic, Germany, Finland,
  United Kingdom, Netherlands, Norway, Poland, and Sweden.

## Closest complete public-data model

The fitted specification contains AERIS PM2.5, population aged 65 years and
older, population density, and GDP per capita. The physician and hospital-bed
series leave too few complete country records for the paper's fuller
specification. The published percentage-above-guideline term requires a
population-weighted exposure surface and is absent from the AERIS monitor
network record.

| Outcome | Published PM2.5 rate ratio | AERIS rate ratio (95% CI) | Countries |
| --- | ---: | ---: | ---: |
| Case rate, day 60 | 1.020 | 0.998 (0.853, 1.168) | 11 |
| Death rate, day 60 | 1.030 | 1.016 (0.806, 1.279) | 11 |
| Case rate, day 80 | 1.020 | 0.971 (0.926, 1.018) | 11 |
| Death rate, day 80 | 1.009 | 0.971 (0.873, 1.079) | 11 |

The underlying regressions use log rates. The table exponentiates each PM2.5
coefficient and interval, yielding a rate ratio per 1 ug/m3 PM2.5.

The strict 75% coverage analysis retains seven countries. Its four estimates
are in `reproduction_model_results.csv`; the one residual degree of freedom
makes those intervals too wide for a useful primary comparison.

## Reproduce

```bash
python acquire_public_inputs.py
python run_aeris_tools.py
python fit_reproduction.py
```

The existing AERIS response cache makes the recorded full-country run
resumable. `aeris_tool_trace.json` stores the tool call and decision log for
each country; `aeris_pm25_2017_country_summary.csv` stores every retrieval
outcome; `analysis_panel.csv` and `reproduction_model_results.*` store the
fitted records and estimates.

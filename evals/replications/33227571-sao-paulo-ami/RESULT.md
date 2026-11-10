# Result

**Status:** first reduced-input reconstruction complete; full historical recovery in progress.

## Completed records

- The public DATASUS SIH/SUS extraction contains **50,826** daily `I21`
  admissions and **5,916** in-hospital deaths across the 39-municipality
  metropolitan region, 1 January 2012 through 31 December 2015.
- The public IBGE study boundary contains all 39 municipalities.
- The public Open-Meteo record contains all 1,461 study-period weather days.
- AERIS requested daily PM2.5, PM10, and NO2 boundary exposure for the full
  period. Its OpenAQ/S3 path found no usable PM2.5, PM10, or NO2 observations.
  The complete tool trace is retained in `data/derived/aeris_tool_trace.json`.
- CETESB historical recovery is running for an AERIS-boundary fallback station.
  It saves each completed day to `data/derived/cetesb_daily_recovery.csv`.

## First fitted result

The first 193 complete NO2-plus-weather days produce a high-pollution-cluster
mean of **35.36** MI admissions per day versus **33.09** in the other two
clusters: **6.88% higher** (bootstrap 95% CI for the difference, 0.24 to 4.33
admissions per day; Mann-Whitney p=0.043).

The published high-pollution cluster had 30.5 admissions per day and a reported
9% increase. This sensitivity uses temperature variation, rainfall, relative
humidity, and NO2. It does not enter the cross-study effect calibration because
the paper reports a cluster contrast and the six-input study-period panel is
still incomplete.

## Fitting rule

`scripts/fit_clusters.py` will fit the full six-input cluster model when PM2.5,
PM10, NO2, temperature variation, rainfall, and humidity share at least 180
days. It will otherwise fit the documented NO2-plus-weather cluster sensitivity
when that panel reaches 180 days. The output will identify the input set used.

No fitted effect is reported until the exposure panel meets one of these rules.

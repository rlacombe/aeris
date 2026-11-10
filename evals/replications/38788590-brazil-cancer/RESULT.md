# Result

Status: completed bounded source-substitution reconstruction.

## Estimate

São Paulo municipality, 2019: **OR 1.006** per 10 ug/m3 increase in 3-day
average PM2.5 (95% CI 0.960--1.054). The fitted log OR is 0.005945 (SE
0.023877).

The panel contains 333 complete lagged days and 12,661 cancer deaths. The
conditional likelihood retained 11,145 deaths across 290 case dates; 1,516
deaths fell in strata without at least four complete same-weekday/same-month
dates. The conditional-score norm at the solution is `3.91e-08`; the
information matrix is positive definite.

## Inputs and model

- Outcome: public 2019 SIM São Paulo state file `DOSP2019.dbc`, filtered to
  São Paulo municipal residents and the paper's stated union of cancer ICD-10
  codes. The retrieved mirror file has SHA-256
  `5e1032b376ae5e3d6e763a84513a42e5bb43a2e61ee07da69fa569c9db961527`.
- Exposure discovery: AERIS boundary tool, using the public IBGE São Paulo
  polygon. It identified 12 OpenAQ PM2.5 locations and returned
  `NO_OBSERVATIONS` for 2019; see `data/derived/aeris_exposure_run.json` and
  `data/derived/openaq_diagnostic_5233.json`.
- Exposure recovery: 343 daily values from CETESB's public historical form for
  AERIS-selected station 31, Cid.Universitária-USP-Ipen. The response-stream
  SHA-256 is `c668d13574c43db8111497c86754969f004f896ef01c3ec7c155cc59c697ffb1`.
- Covariates: daily São Paulo-centroid temperature and relative humidity from
  Open-Meteo, plus Brazilian national statutory holidays.
- Model: weighted conditional logistic likelihood with same-weekday and
  same-month referent days. PM2.5, temperature, and relative humidity use
  three-day averages (lag 0--2); PM2.5 is scaled per 10 ug/m3.

## Comparison target

Yu et al. report OR 1.04 (95% CI 1.03--1.04) for the 2000--2019 national
analysis and OR 1.01 (95% CI 1.00--1.02) for 2015--2019. The reconstruction
uses one municipality and one calendar year, so it is retained as a completed
study-specific reconstruction rather than entered in the cross-study effect
calibration table.

## Audit files

- `source_manifest.json`: source URLs and scope.
- `data/raw/sim_download.json`: SIM source URL, failed official attempt, byte
  count, and SHA-256.
- `data/raw/boundary_download.json`: IBGE boundary URL and SHA-256.
- `data/derived/weather_download.json`: Open-Meteo request URL and coverage.
- `data/derived/aeris_exposure_run.json`: AERIS tool call and its result.
- `data/derived/cetesb_pm25_download.json`: official historical recovery
  request, coverage, and response-stream SHA-256.
- `data/derived/analysis_panel_cetesb_recovery.csv` and
  `data/derived/panel_summary_cetesb_recovery.json`: model input panel.
- `outputs/effect_result_cetesb_recovery.json`: fitted effect and coefficients.

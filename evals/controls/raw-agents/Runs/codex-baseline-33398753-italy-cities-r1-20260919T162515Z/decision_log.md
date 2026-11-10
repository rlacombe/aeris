# Independent reanalysis decision log

Study: PMID 33398753, “Italian provincial capitals COVID-19.” Run date: 2026-09-19 UTC.

## Target recovered from the article

The article describes a cross-sectional analysis of 55 randomly selected Italian provincial-capital cities. The outcome is cumulative infected individuals on 17 March, 7 April, and 27 April 2020. The principal exposure is the total number of 2018 days exceeding a PM10 or ozone limit. The stated multivariable model is OLS with log cumulative infections as the dependent variable and log air-pollution exceedance days plus log 2019 population density as explanatory variables. The primary estimate here corresponds to the 17 March outcome; the two later article dates are also fitted and retained in `model_estimates.csv`.

## Pre-fit reconstruction decisions

1. The publication does not name the randomly selected 55 cities. Exact sample reconstruction is therefore impossible. I used the complete, public official provincial reporting universe (107 geographic records with coordinates), rather than choosing a new 55-city sample.
2. The official Civil Protection source supplies cumulative confirmed COVID-19 cases at province level, not city level. The provincial total is used as the outcome and this outcome-unit substitution is explicit in `result.json`.
3. To meet the independent-exposure requirement, exposure was calculated without author values or author-derived data. Hourly 2018 PM10 and ozone at each provincial-capital coordinate were requested from Open-Meteo's public air-quality service (CAMS reanalysis). A day counted if mean PM10 exceeded 50 micrograms/m3 or the maximum rolling 8-hour ozone mean exceeded 120 micrograms/m3. This replaces the article's monitor-based Legambiente variable; it is not claimed to be numerically interchangeable.
4. The covariate is Eurostat 2019 NUTS3 population density, rather than the article's municipal density, so its area is consistent with the public provincial outcome.
5. The model was fit only on rows with a positive outcome, positive exposure, and a direct density match. No missing density or zero exposure was imputed, offset, or otherwise transformed.

## Coverage decisions

There were 107 eligible official provincial records. Four had no direct Eurostat 2019 NUTS3-density name match: Aosta, Bolzano, Reggio di Calabria, and Sud Sardegna. Three had zero CAMS-derived exceedance days (Aosta, Ascoli Piceno, Teramo); their log exposure is undefined. The final complete-case analysis includes 100 provinces, and each has all 365 modeled 2018 exposure days. These exclusions are visible in `analysis_panel.csv`.

## Model and result

For each of the three outcomes, the executable code fits `OLS(log(cases) ~ log(exceedance_days) + log(population_density))` with an intercept and conventional model-based 95% confidence intervals. It does not add the article's weather variables because the displayed principal multiple-regression table uses pollution and density; their omission from this fit is a model choice, not a failed retrieval.

The primary 17 March coefficient for log exceedance days is 0.7103 (95% CI 0.5209 to 0.8997; N=100). Interpretation is associative: conditional on provincial population density in this reconstructed data set, a 1% higher modeled number of limit-exceedance days is associated with a 0.71% higher cumulative confirmed-case count. This is not a causal effect and is not an exact replication.

## Retrieval and retry record

`request_log.json` records the URL, timestamp, HTTP status, byte count, attempt, and any delay for every request in this run. All requests completed on their first attempt; no retry schedule was invoked. Raw retrieved responses and their checksums are recorded in `source_manifest.json` and retained under `raw/`.

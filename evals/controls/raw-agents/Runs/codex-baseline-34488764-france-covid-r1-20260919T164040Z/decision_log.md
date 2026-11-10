# Independent reanalysis decision log

Study: PMID 34488764, “France COVID-19”. Run date: 2026-09-19 UTC.

## Target reconstructed from the supplied article

* Outcome: cumulative COVID-19 deaths in hospital, by French mainland department, expressed by the authors per 100,000 population.
* Pollutant/exposure: department mean annual PM2.5, averaged over 1999–2016; continuous and PM2.5 quartiles.
* Geography/unit: 96 mainland-France departments (NUTS 3), one cross-section at each of nine snapshots.
* Period: 01 May, monthly 01 June–01 December, and 31 December 2020.
* Principal model: negative-binomial regression, apparently using the count outcome/rate formulation, PM2.5 and temperature jointly, with intensive/resuscitation beds, medical density, age 60+, male share, unemployment, poverty, urban share, population density, and diabetes prevalence as adjustment variables. The article reports exponentiated coefficients as mortality-rate ratios.

## Retrieval and coverage decisions

1. Retrieved the Ministry of Health’s public `covid-hospit` department daily series through the data.gouv.fr dataset API. `sexe=0` was selected as the all-sex departmental cumulative series. The executable extraction writes 864 rows (96 departments × 9 dates) to `outcome_table.csv`; missing department-date combinations are checked programmatically.
2. The authors’ exposure values, tables, code, and derived datasets were not used. I located the independent public ACAG global/regional PM2.5 catalogue, which describes its 1998–2023 annual/monthly gridded estimates and provides a 0.1-degree Europe directory. The public catalogue page and Box shared-folder metadata were retrieved. The nested Europe grid payload could not be obtained from the Box delivery endpoint in this run: the direct folder-download request returned HTTP 512 with zero bytes, while non-root nested-folder requests returned no public item payload. The source-access evidence is retained under `/output`.
3. No department PM2.5 values were therefore constructed. An empty `exposure_table.csv` is intentional and explicitly records no invented assignment.
4. The article’s ten adjusted covariates were not available as a complete independently retrieved 96-department panel during this run. No outcome, geography, period, exposure, covariate, or model substitution was made.

## Modeling decision

The official outcome panel is complete, but the analytic panel is not: it has zero independent exposure rows and zero complete covariate rows. Per the task’s fail-closed requirement, the negative-binomial principal comparison was **not run**. A reduced unadjusted model, a later-period PM2.5 surrogate, or author-provided values would change the scientific task and is not reported.

## Retry record

The official data download used curl’s identical-request transport retry option (up to five retries); it completed on the initial successful request. The ACAG catalogue request completed successfully. The Box nested-folder attempts were inspected as access/delivery evidence, not retried with altered scientific inputs. No HTTP 429/5xx eligible source-data request required a retry schedule.

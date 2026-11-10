# Reproduction Status: PMID 34488764

## Target

Tchicaya et al. estimated a negative-binomial COVID-19 hospital mortality-rate
model for 96 mainland French departments. The primary comparison here is the
published May 1, 2020 PM2.5 rate ratio: `1.244` per 1 µg/m3 (95% CI `1.083`
to `1.428`).

## Inputs

- Outcome: official `covid_hospit` historical department file from data.gouv.fr,
  resource `63352e38-d353-4b54-bfd1-f1b3ee1cabd7`; deaths are the `sexe=0`
  cumulative hospital-death count on 2020-05-01.
- Department codes: French government `geo.api.gouv.fr/departements` endpoint.
- Covariates: the authors' CC-BY workbook, *COVID19_European data_new.xlsx*,
  Mendeley Data DOI `10.17632/2ghxnrkr9p.4`. The run uses population,
  temperature, age 60+, female share, population density, diabetes prevalence,
  and intensive-care beds.
- Boundaries: geoBoundaries France ADM2, release commit `9469f09`, boundary ID
  `FRA-ADM2-29444166`.
- Exposure replacement: AERIS/OpenAQ 2019 annual PM2.5 monitor-network record,
  reconstructed independently for each department. It replaces the paper's
  1999-2016 satellite-derived PM2.5 surface.

## Outcome Validation

The independently acquired outcome panel has 96 mainland departments. Its
May 1 mortality-rate distribution is 19.76 mean, 20.00 standard deviation,
1.31 minimum, and 104.01 maximum deaths per 100,000. The paper reports 19.8,
20.1, 1.3, and 106.3, respectively.

## AERIS Progress

Paris has a completed AERIS 2019 PM2.5 record: 14.24 µg/m3 from two stations
and 97.5% daily coverage. The resumable runner is ready for all 96 departments.
The full queue is temporarily paused while concurrent benchmark workers use the
same OpenAQ key; its SQLite cache preserves all already-completed requests.

## Reconstructed Fit

The 2019 AERIS/OpenAQ v3 run attempted all 96 departments. Sixty-four met the
75% daily-coverage gate and 63 had complete outcome and covariate data for the
negative-binomial model with a log population offset.

| PM2.5 rate ratio per 1 ug/m3 | Published | AERIS/OpenAQ reconstruction |
| --- | ---: | ---: |
| Estimate | 1.244 | 1.049 |
| 95% CI | 1.083 to 1.428 | 0.953 to 1.153 |

The paper uses a 1999--2016 satellite-derived department mean. AERIS replaces
that field with a 2019 OpenAQ monitor-network mean. The fit uses the paper's
public outcome and covariate fields; the exposure substitution is recorded in
`exploratory_model_result.json`.

# PMID 39377000: U.S. stroke mortality

This directory reconstructs *Inequities in air pollution on stroke mortality
among Older Americans: a U.S. nationwide analysis* (2024), PMID 39377000.

## Published target

The paper reports an adjusted county-level 2016--2020 coefficient of **1.89
additional ischemic-stroke deaths per 100,000 residents per 1 microgram/m3
PM2.5**. Its model includes county stroke-risk and socioeconomic covariates.

## Reconstructed public analysis

The replication uses the fully public CDC Atlas county export. It supplies a
2019 age-standardized all-stroke mortality rate for adults 65+; its public
schema does not separate ischemic stroke. The model pairs that outcome with
2019 AERIS PM2.5 estimates and the paper's covariate families:

- CDC PLACES: coronary heart disease, hypertension, diabetes, high cholesterol,
  obesity, smoking, and uninsured prevalence.
- County Health Rankings: median household income, child-poverty proxy, income
  inequality, and access-to-exercise proxy for park access.

`download_wonder_outcomes.py` retains the D76 ICD-10 I63 query used to explore
a county ischemic-stroke outcome. The public query endpoint did not return a
usable export in this environment. It is not needed for the completed public
reconstruction.

## Run commands

```bash
python build_atlas_proxy_panel.py
python run_aeris_tools.py
python build_adjusted_public_panel.py
python fit_adjusted_public_model.py
```

`run_aeris_tools.py` selects every tenth county after FIPS sorting (303 of
3,022 counties) and reconstructs each 2019 annual PM2.5 estimate exclusively
through AERIS/OpenAQ. Forty-seven counties meet its 50% completeness gate;
forty-six have all public covariates.

## Files

- `atlas_all_stroke_65plus_county_2019.csv`: public CDC Atlas outcome panel.
- `aeris_cohort_2019_systematic_10pct.csv`: pre-specified AERIS sample.
- `aeris_pm25_2019_systematic_10pct.csv`: reconstructed annual AERIS estimates.
- `aeris_tool_trace.json`: AERIS tool calls and decision log.
- `adjusted_public_analysis_panel.csv`: final 46-county analysis panel.
- `adjusted_public_model_coefficients.csv`: robust standard errors and model
  coefficients.
- `adjusted_public_model_result.json`: fitted PM2.5 effect and diagnostics.

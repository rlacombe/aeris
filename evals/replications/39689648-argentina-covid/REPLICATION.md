# Reproduction specification

## Published analysis

The paper analyzed 332 Argentine districts with population density at least 5
people per km2. It correlated 2019 gridded PM2.5 concentration, sanitary
vulnerability, and COVID-19 positive-test, ICU-admission, and death rates per
100,000 people from 1 March 2020 through 1 January 2021.

Published PM2.5 correlations: positive tests `r=-0.09`, ICU admissions
`r=-0.16`, and deaths `r=-0.11`.

## Reconstruction target

The reconstruction retains the official outcome date window, department-level
geography, and ecological correlation design. It substitutes an AERIS/OpenAQ
monitor-network PM2.5 record for the paper's gridded ACAG product.

The published SVI is a census-block index derived from health-facility distance
and census measures. Its public map is available but its machine-download API
has not yet yielded a stable department file. The first fitted comparison will
therefore report unadjusted PM2.5-outcome correlations, followed by the SVI
interaction model when the mapped index is acquired and joined.

## Included outcome definition

`build_outcomes.py` retains records with `clasificacion_resumen` containing
`Confirmado`, uses diagnosis date for the paper's window, and sums confirmed
cases, ICU admissions, and deaths by residence department.

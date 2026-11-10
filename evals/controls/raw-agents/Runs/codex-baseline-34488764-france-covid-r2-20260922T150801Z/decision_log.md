# Reanalysis decision log

## Locked reconstruction target

- Study: PMID 34488764, *France COVID-19*.
- Outcome: cumulative COVID-19 deaths in hospital, by metropolitan French department (NUTS-3); public Ministry of Health series (`dc`, `sexe=0`).
- Times: 1 May, 1 June, 1 July, 1 August, 1 September, 1 October, 1 November, 1 December, and 31 December 2020.
- Pollutant: long-term PM2.5, published as the 1999--2016 department mean, modeled continuously (per 1 µg/m3) and as quartiles.
- Published model: separate adjusted negative-binomial regressions at each date, including PM2.5 and 2001--2012 temperature, health-service variables, demographic/socioeconomic variables, population density, and diabetes prevalence. The article calls the exponentiated coefficients mortality-rate ratios; it does not state the count-model offset explicitly.
- Comparison contrasts declared here: continuous PM2.5 +1 µg/m3; Q2 vs Q1, Q3 vs Q1 (primary quartile contrast), and Q4 vs Q1. Native coefficient is log rate ratio and transformed value is exp(coefficient), a positive mortality rate ratio.

## Data and exposure decisions

1. Used the public data.gouv.fr hospital series, rather than an author-derived outcome table. The extracted panel has 96 departments at all nine target dates (864 rows).
2. Used an independent public source for PM2.5: EEA validated air-quality statistics, queried identically for France, 2016, PM2.5, annual mean. This is not NASA/SEDAC/GOME and contains no author exposure values.
3. The independent query yielded only two urban station annual means (Talence and Saint-Quentin), each with approximately 94% data coverage. It cannot provide a department mean for the study's 96 units, nor its 1999--2016 long-term mean. The analysis panel therefore deliberately has missing PM2.5 rather than assigning stations to departments or extrapolating.
4. The article claims its full data set was publicly accessible, but supplies neither a usable dataset URL nor a copy in the supplied materials. No author table was used. `sanitization.json` documents the empty retained/dropped lists; this is intentional because nothing was inspected or modeled from such a table.
5. No covariate, population, outcome, geography, or period substitution was made to force a fit. The missing population offset and published covariates are additional blockers, but the exposure-coverage failure independently prevents the principal comparison.

## Modeling decision

No negative-binomial model was fit. Fitting on the two monitor locations, treating monitor readings as 96 department means, using a one-year measurement as an 18-year average, dropping all adjustment variables, or choosing an unreported outcome model would be an undisclosed scientific change. `model_output.json` is an explicit non-execution record, not an estimate.

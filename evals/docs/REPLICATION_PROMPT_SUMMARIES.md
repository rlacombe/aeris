# Replication Prompt Summaries

## Status

These are reconstructed summaries of the instructions used for each AERIS
source-substitution reanalysis. They summarize the project conversation and
the execution records. They are not verbatim transcripts.

## Shared instruction

For each study, reconstruct the reported analysis as closely as public inputs
allow. Use the article to identify the study unit, time window, outcome,
pollutant, model, and covariates. Retrieve outcomes and covariates from the
named public sources. Rebuild the pollutant record through AERIS and public
ambient-data sources; never use the article's exposure values. Keep the code,
source manifest, AERIS trace, coverage diagnostics, analysis panel, model
output, and a short result note in the study directory. State every geographic,
temporal, exposure, outcome, and covariate substitution in the result record.

Run a fit when the reconstructed panel supports the study's main comparison.
When it does not, stop with an evidenced blocker rather than manufacturing an
effect estimate.

## Study-specific summaries

### PMID 33227571, São Paulo acute myocardial infarction

Recreate the 39-municipality daily environmental-cluster analysis using public
SIH/SUS I21 admissions, public municipality boundaries, AERIS boundary
exposures, and Open-Meteo weather. Preserve the paper's study period and fit
the reported cluster model after the daily panel is complete.

### PMID 33398753, Italian provincial capitals COVID-19

Recreate the city-level COVID-19 comparison with public city outcomes and
AERIS PM10. Calculate the published PM10-exceedance contrast for 2018 and fit
the closest public-data model. Expand city coverage where the AERIS record
supports it; record the final city count and coverage.

### PMID 33484722, OECD COVID-19

Recreate the country-level day-60 and day-80 case and death models with WHO
COVID-19 data, World Bank covariates, and AERIS country-boundary PM2.5. Use
the closest complete covariate set. Report the country count and distinguish
the OpenAQ monitor-network mean from the article's population-weighted
exposure product.

### PMID 33585383, China COVID-19

Use the authors' public prefecture table only for outcomes, population,
density, and place labels. Remove all author pollution columns. Reconstruct
2014--2016 PM2.5 with AERIS and fit the paper's prefecture-level Kendall
correlation. Split retrieval into resumable annual batches so each archived
interval remains tractable.

### PMID 34004167, Northern Italy COVID-19

Recreate the regional COVID-19 analysis from public Civil Protection outcomes
and AERIS boundary aggregation. Seek the published PM2.5 exposure first. If
the public archive lacks a fit-ready PM2.5 panel, document the coverage result;
any NO2 analysis remains a separately labeled supported-pollutant analysis.

### PMID 34260961, Israel COVID-19

Use official municipality-level COVID-19 and census sources with AERIS annual
PM2.5 for 2016--2019. Fit the reported municipal model only if the exposure
has spatial variation. Audit the OpenAQ/S3 historical record before deciding
that the PM2.5 coefficient is identifiable. Keep any NO2 exploration separate
from the PM2.5 target.

### PMID 34389545, Western U.S. wildfire COVID-19

Use the authors' public package only for county boundaries, population, and
daily COVID-19 outcomes. Exclude its exposure, smoke, weather, mobility, and
merged-analysis files. Rebuild daily PM2.5 with AERIS, apply the stated
coverage gate, and fit the closest available county fixed-effects lag model.

### PMID 34488764, France COVID-19 mortality

Recreate the department-level negative-binomial analysis with public French
COVID-19 outcomes and covariates. Replace the study's satellite-derived
long-term PM2.5 with an independently reconstructed AERIS/OpenAQ annual
department record. Preserve the target date, geography, and modelling family.

### PMID 36197352, Taubaté COVID-19 admissions

Recreate the three-municipality daily admissions analysis with public SIH/SUS
outcomes, AERIS monitor discovery, public historical station data when OpenAQ
ends, and public weather. Preserve the paper's dates, pollutants, lag scan,
and negative-binomial model. Stop if a complete daily outcome panel cannot be
obtained.

### PMID 36383802, São José dos Campos COVID-19 admissions

Recreate the daily lagged O3 and NO2 admissions models with public SIH/SUS,
AERIS exposure, and public weather. If the official monthly source fails to
deliver, use the cited public SIVEP-Gripe route only as a clearly labeled
bounded outcome substitution.

### PMID 38182658, United Kingdom COVID-19

Recreate the four-nation COVID-19 panel using public UKHSA outcomes,
geoBoundaries, public weather, and AERIS boundary PM2.5. Fit the closest
available model and report both the article's nation-day count and the
reconstructed count.

### PMID 38249516, Alaska wildfire and asthma

Construct the 11 documented behavioural-health regions and retrieve public
annual asthma estimates. Reconstruct annual PM2.5 with AERIS and fit the
paper's correlation only when both the outcome and exposure panel are
available. Record the missing public component if either panel fails.

### PMID 38788590, Brazil cancer mortality

Recreate a transparent bounded case-crossover analysis using public DATASUS
mortality outcomes, AERIS-selected PM2.5 monitoring, public historical station
recovery when the OpenAQ payload is absent, and public weather. Preserve the
published lag and referent rule. Label the São Paulo 2019 scope as a bounded
source-substitution analysis rather than a national rerun.

### PMID 39377000, U.S. stroke mortality

Use public county stroke outcomes and the paper's covariate families with
AERIS 2019 PM2.5. Retrieve every tenth county in pre-specified FIPS order,
apply the coverage gate, fit the public adjusted model, and express the effect
on the same per-10 micrograms per cubic metre scale as the comparison.

### PMID 39689648, Argentina COVID-19

Build the department-level COVID-19 panel from the official Ministry of Health
archive and public boundaries. Reconstruct PM2.5 through AERIS/OpenAQ with S3
fallback. Use the strict within-boundary assignment first, with any
representative-point approach clearly labeled as a sensitivity analysis. Fit
only when the department panel has sufficient coverage.

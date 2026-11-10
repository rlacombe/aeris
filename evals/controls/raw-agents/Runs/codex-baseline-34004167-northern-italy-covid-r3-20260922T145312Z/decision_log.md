# Decision log

## Locked reconstruction target

- Study: PMID 34004167, *Effect of short- and long-term exposure to atmospheric pollution on COVID-19 risk and fatality: analysis of the first epidemic wave in Northern Italy*.
- Statistical units: Lombardy and Veneto, one record per region-day.
- Period: 21 February through 19 May 2020 (89 calendar days; 178 region-days).
- Outcomes: daily COVID-19 cases and deaths; the paper also analyzed fatality (deaths/cases).
- Pollutants/exposure: NO2, O3, PM2.5, PM10, and SO2; STAP is region-day mean and LTAP is the 2013-to-19 May 2020 mean.
- Covariate: LOCK, 1 from 22 February 2020.
- Intended model: log-link GEE for count outcomes with AR(1) working correlation, including STAP, LTAP, and LOCK. The paper reports a one-unit concentration contrast for each pollutant/outcome.

## Outcome recovery and sanitization

Retrieved the Italian Civil Protection regional CSV directly from its public repository. Before inspection/modeling, `code/reanalysis.py` retains only `data`, `denominazione_regione`, `nuovi_positivi`, `deceduti`, and `totale_casi`; all remaining source fields are listed in `outcome_sanitization.json`. No author-provided analysis table was used.

The CSV supplies both regions from 24 February through 19 May: 86 of 89 target dates and 172 of 178 region-days. Its first available date is after the paper's stated lockdown start. Thus the reconstructed `lock` field is exactly 1 for every available record; it has no variation.

## Exposure recovery

The authors' EEA-derived exposure values were not downloaded or used. An official ARPA Lombardia annual 2020 workbook was retrieved as an independent candidate; inspection shows annual station-level indicators, which cannot create STAP or 2013-2020 LTAP. ARPAV's public historical-data page explicitly requires an email address and sends requested CSV by email. No email request was made. OpenAQ v3 returned HTTP 401 once; it was not blindly retried under the supplied policy.

## Modeling decision

No model was fitted. The locked model requires independent STAP and LTAP for every declared pollutant and both regions, which were not recovered. Independently, `LOCK` is perfectly constant in the available outcome panel, so the stated adjusted model cannot estimate its lockdown coefficient. Omitting LOCK, using author exposure data, treating annual summaries as daily data, or narrowing to one pollutant would all be undisclosed scientific substitutions. Model status and exact rationale are in `model_output.txt`.

# Decision log — PMC7826117 independent reanalysis

- The article defines the central fitted comparison as OLS models of log national COVID-19 morbidity/mortality rates on country characteristics at days 60 and 80 after the first case. This run declares day-80 confirmed-case rate as primary and also fits the other three Table-1 outcome/day contrasts.
- Outcome unit: country; outcome is cumulative confirmed cases or deaths divided by population, expressed per 100,000 before natural-log transformation. Day 1 is each country's first date with a positive JHU cumulative count.
- Exposure: World Bank indicator `EN.ATM.PM25.MC.M3`, 2017, population-weighted ambient PM2.5 in ug/m3. This is independently retrieved and is not any author-released pollution/exposure file.
- Covariates reproduce Table 1's stated structure: percent age 65+, density, GDP, physicians, hospital beds, and PM2.5. The published physician (2017, else the larger 2016/2015) and hospital-bed (2015, else the larger 2014/2013/2012) fallback rules are implemented. World Bank indicator definitions and requested years are recorded in code and manifest.
- JHU CSSE country time series replaces the article's WHO daily series. This is a recorded source substitution, not a change in outcome construct.
- Model: unweighted Gaussian OLS, natural log outcome, intercept and six listed covariates. Coefficient inference uses statsmodels OLS conventional 95% t intervals. Exponentiating the PM2.5 coefficient yields the positive rate ratio per 1 ug/m3.
- The author-table PM2.5-exposure-above-guideline covariate is omitted, because the reconstruction must use independently sourced pollution and the public independent source selected provides the concentration measure. This is a declared model substitution.
- No author-designated analytic table, derived exposure, fitted value, or analysis code was inspected or used. `sanitization_record.json` documents the guardrail function and its non-use.

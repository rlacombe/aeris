# Decision log

- Identified the article's principal analysis as cross-sectional county-level OLS: age-65+ ischemic-stroke mortality rate (ICD-10 I63, I65-I66), US counties, 2016--2020, PM2.5 in ug/m3. The stated adjusted model includes CAD, HTN, HLD, diabetes, obesity, smoking, income, Gini, poverty, uninsured, and park access.
- Treated the all-counties adjusted ischemic-stroke model as the principal comparison. The article reports its native contrast as change in deaths per 100,000 per 1 ug/m3 PM2.5; it is not an OR/RR/outcome-ratio model.
- Did not use author pollution values, derived fields, tables, or code. No author-designated outcome/covariate table was available. The sanitization rule and empty retained/dropped lists are in `sanitization_columns.json`.
- Retrieved EPA AQS annual-concentration-by-monitor archives for 2016 and 2020. Exposure is a within-county mean of monitor-level annual arithmetic means, restricted to parameter code 88101 (PM2.5 mass). This is explicitly an independent but incomplete geographic exposure assignment.
- Opened and accepted the CDC WONDER Underlying Cause of Death 1999--2020 request form, then made one fixed county/age/cause/year query. It did not return an outcome table. No retry was made because this was not a transient transport failure; the response is retained.
- Did not execute OLS or report an effect. A complete 2016--2020 county panel with the locked outcome, independent exposure, and covariates is absent. No coverage standard was relaxed.

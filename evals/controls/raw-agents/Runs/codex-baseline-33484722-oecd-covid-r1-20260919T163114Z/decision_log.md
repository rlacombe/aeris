# Decision log

- Target inferred from Table 1: country-level log rate of confirmed COVID-19 cases per 10,000 population on the 80th day after the first confirmed case; 36 OECD countries as listed in the paper; PM2.5 annual population-weighted exposure (2017) is the focal pollutant.
- Day numbering counts the first date with a positive cumulative case count as day 1, hence day 80 is first-positive date + 79 days. All 36 country-specific day-80 dates occur in the JHU series.
- The article's WHO daily outcome data are no longer the input used here. JHU CSSE cumulative country data are an independently downloaded public outcome substitute. This changes the data source but not outcome definition, countries, or timing rule.
- The exposure table was constructed directly from the World Bank API, not from any author-provided data. It uses indicator `EN.ATM.PM25.MC.M3` (2017) and includes the Table 1 exposure-above-guideline indicator `EN.ATM.PM25.MC.ZS` (2017).
- The covariate selection rules follow the article: elderly percentage (2018); density and population (2019); physicians (2017, otherwise the larger nonmissing 2015/2016 value); hospital beds (2015, otherwise the larger nonmissing 2012--2014 value). World Bank GDP per capita (current USD, 2019) replaces the article's OECD GDP measure; this is a disclosed covariate substitution.
- The paper did not state its GDP unit or a regression intercept. OLS was fit with an intercept and its published Table 1 covariate set. No weighting or robust-standard-error change was made.
- The current World Bank physician series has no United States observation in the article's permitted 2015--2017 window. The U.S. was therefore excluded listwise; no later year was substituted. The fit has 35 complete country rows.
- Transport note: an attempted OWID download failed three times due to DNS resolution (curl exit 6). The subsequently used JHU and World Bank requests succeeded. The failed source was not treated as data evidence.

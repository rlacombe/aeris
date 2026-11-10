# Result

The completed public reconstruction fits the paper's covariate families in 46
counties with a 2019 AERIS PM2.5 record that passed the 50% daily-completeness
gate. The adjusted coefficient is **3.01 additional all-stroke deaths per
100,000 adults aged 65+ per 1 microgram/m3 PM2.5** (HC3 95% CI -10.10 to
16.11; p=0.653; model R-squared=0.632).

The paper reports **1.89 additional ischemic-stroke deaths per 100,000 per
1 microgram/m3 PM2.5** from its 2016--2020 adjusted model. The two estimates
have the same coefficient scale and direction. The AERIS reconstruction uses a
2019 all-stroke CDC Atlas outcome because the public Atlas schema does not
separate ischemic stroke; it uses public proxies for county poverty and park
access. `adjusted_public_model_result.json` records each substitution and the
complete model specification.

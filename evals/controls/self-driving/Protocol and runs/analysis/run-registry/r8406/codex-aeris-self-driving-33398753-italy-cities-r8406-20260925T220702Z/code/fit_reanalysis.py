#!/usr/bin/env python3
"""Fit the locked log-log OLS models using the derived AERIS PM10 metric."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import statsmodels.api as sm

OUT = Path('/output')
base = pd.read_csv(OUT/'data'/'outcome_covariate_panel.csv')
exp = pd.read_csv(OUT/'data'/'pm10_exposure_2018.csv')
panel = base.merge(exp, on='province', how='left', validate='one_to_one')
panel['eligible_loglog'] = (panel.pm10_exceedance_days_gt50 > 0)
for c in ['infections_20200317','infections_20200407','infections_20200427',
          'density_2019_per_km2','pm10_exceedance_days_gt50']:
    panel['log_'+c] = np.where(panel[c] > 0, np.log(panel[c]), np.nan)
panel.to_csv(OUT/'data'/'analysis_panel.csv', index=False)

fit = panel.loc[panel.eligible_loglog].copy()
if len(fit) < 10:
    raise RuntimeError('insufficient nonzero PM10-exceedance units for log-log model')
X = sm.add_constant(fit[['log_pm10_exceedance_days_gt50','log_density_2019_per_km2']])
results = {'analysis':'OLS log-log; exposure metric: observed 2018 daily PM10 >50 ug/m3 count',
           'n_sample_frame':int(len(panel)), 'n_exposure_observed':int(panel.observed_days.notna().sum()),
           'n_exposure_positive_complete_case':int(len(fit)), 'models':{}}
chunks=[]
for d in ['20200317','20200407','20200427']:
    y = fit['log_infections_'+d]
    model = sm.OLS(y, X).fit()
    beta = float(model.params['log_pm10_exceedance_days_gt50'])
    se = float(model.bse['log_pm10_exceedance_days_gt50'])
    ci = model.conf_int().loc['log_pm10_exceedance_days_gt50'].tolist()
    ratio = float(np.exp(beta*np.log(2)))
    ratio_ci = [float(np.exp(z*np.log(2))) for z in ci]
    results['models'][d] = {
        'outcome':f'cumulative confirmed infections on {d}', 'nobs':int(model.nobs),
        'parameters':{k:float(v) for k,v in model.params.items()},
        'standard_errors':{k:float(v) for k,v in model.bse.items()},
        'pvalues':{k:float(v) for k,v in model.pvalues.items()},
        'r_squared':float(model.rsquared), 'residual_df':float(model.df_resid),
        'pm10_beta':beta, 'pm10_beta_ci95':ci,
        'outcome_ratio_per_doubling_pm10_exceedance_days':ratio,
        'outcome_ratio_ci95':ratio_ci,
        'source':'statsmodels OLS conventional covariance'
    }
    chunks += [f'\n### Outcome {d}\n', model.summary().as_text(),
               f'\nDoubling PM10 count ratio: {ratio:.6f}; 95% CI {ratio_ci[0]:.6f}, {ratio_ci[1]:.6f}\n']
(OUT/'model_output.txt').write_text('\n'.join(chunks))
(OUT/'model_output.json').write_text(json.dumps(results, indent=2))
print(json.dumps(results, indent=2))

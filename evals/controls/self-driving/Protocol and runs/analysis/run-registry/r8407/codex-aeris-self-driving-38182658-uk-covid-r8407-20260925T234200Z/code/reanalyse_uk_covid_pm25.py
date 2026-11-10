"""Executable bounded reanalysis of Hossain et al. (2024).

Uses public historical UK nation cumulative indicators (GitHub preservation of
dashboard data) and Open-Meteo archive/reanalysis products.  It deliberately
does not read the article's exposure values or reported effects.
"""
import json, os
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
import statsmodels.api as sm

OUT = '/output'
DATA = OUT + '/data'
NATIONS = ['England', 'Northern Ireland', 'Scotland', 'Wales']
START, END = '2020-03-26', '2020-08-01'  # last complete retained outcome date

def daily_weather(path, nations):
    x = json.load(open(path))
    x = x if isinstance(x, list) else [x]
    frames = []
    for nation, z in zip(nations, x):
        d = pd.DataFrame(z['daily'])
        d['date'] = pd.to_datetime(d.pop('time'))
        d['nation'] = nation
        d['temperature_c'] = d.pop('temperature_2m_mean')
        d['sunshine_hours'] = d.pop('daylight_duration') / 3600
        d['humidity_pct'] = d.pop('relative_humidity_2m_mean')
        frames.append(d[['nation','date','temperature_c','sunshine_hours','humidity_pct']])
    return pd.concat(frames)

def daily_pm(path, nations):
    x = json.load(open(path))
    x = x if isinstance(x, list) else [x]
    frames=[]
    for nation, z in zip(nations, x):
        d=pd.DataFrame(z['hourly'])
        d['date']=pd.to_datetime(d.pop('time')).dt.normalize()
        d['nation']=nation
        frames.append(d.groupby(['nation','date'],as_index=False)['pm2_5'].mean())
    return pd.concat(frames)

# Dashboard archive records cumulative counts.  Reindexing preserves daily
# calendar support; negative revisions are excluded rather than converted to
# artificial events.
x = pd.read_csv(DATA + '/covid-19-indicators-uk.csv')
x['Date'] = pd.to_datetime(x.Date)
rows=[]
for nation in NATIONS:
    q=x[(x.Country==nation)&x.Indicator.isin(['ConfirmedCases','Deaths'])].pivot(index='Date',columns='Indicator',values='Value').sort_index()
    q=q.reindex(pd.date_range(q.index.min(), q.index.max(), freq='D')).ffill()
    q['cases']=q['ConfirmedCases'].diff(); q['reported_deaths']=q['Deaths'].diff()
    q['nation']=nation; q['date']=q.index
    rows.append(q[['nation','date','cases','reported_deaths']])
outcomes=pd.concat(rows,ignore_index=True)
outcomes['death_attributed'] = outcomes.groupby('nation')['reported_deaths'].shift(-8)
outcomes.loc[(outcomes.cases<=0)|(outcomes.death_attributed<0)|
             (outcomes.death_attributed>outcomes.cases), ['cases','death_attributed']] = np.nan

weather = pd.concat([
    daily_weather(DATA+'/openmeteo_england.json',['England']),
    daily_weather(DATA+'/openmeteo_all.json',['Northern Ireland','Scotland','Wales'])])
pm = pd.concat([
    daily_pm(DATA+'/openmeteo_air_england.json',['England']),
    daily_pm(DATA+'/openmeteo_air_other.json',['Northern Ireland','Scotland','Wales'])])
panel=outcomes.merge(weather,on=['nation','date'],how='left').merge(pm,on=['nation','date'],how='left').sort_values(['nation','date'])
for c in ['pm2_5','temperature_c','sunshine_hours','humidity_pct']:
    panel[c+'_lag10_mean']=panel.groupby('nation')[c].transform(lambda z:z.rolling(11,min_periods=11).mean())
panel['weekday']=panel.date.dt.day_name()
panel['in_target_window']=panel.date.between(START,END)
panel.to_csv(OUT+'/analysis_panel.csv',index=False)

fit=panel[panel.in_target_window].dropna(subset=['cases','death_attributed','pm2_5_lag10_mean','temperature_c_lag10_mean','sunshine_hours_lag10_mean','humidity_pct_lag10_mean']).copy()
# A transparent bounded linear distributed-lag approximation.  The 11-day
# average preserves the article's max lag scale but cannot reproduce its
# spline DLNM without the original backprojection delay distribution.
fit['prop']=fit.death_attributed/fit.cases
formula='prop ~ I(pm2_5_lag10_mean / 10) + temperature_c_lag10_mean + sunshine_hours_lag10_mean + humidity_pct_lag10_mean + C(nation) + C(weekday)'
model=smf.glm(formula, data=fit, family=sm.families.Binomial(), freq_weights=fit.cases).fit(cov_type='HC1')
coef=model.params['I(pm2_5_lag10_mean / 10)']; se=model.bse['I(pm2_5_lag10_mean / 10)']
effect={'term':'PM2.5 11-day mean, per 10 ug/m3','log_odds_ratio':float(coef),'se_robust':float(se),'odds_ratio':float(np.exp(coef)),'ci95_or':[float(np.exp(coef-1.96*se)),float(np.exp(coef+1.96*se))], 'p_value':float(model.pvalues['I(pm2_5_lag10_mean / 10)'])}
with open(OUT+'/model_output.txt','w') as f:
    f.write(model.summary().as_text()+'\n\nEffect JSON:\n'+json.dumps(effect,indent=2)+'\n')
coverage=(panel[panel.in_target_window].groupby('nation').agg(rows=('date','size'), fit_ready=('cases',lambda z:z.notna().sum()), pm_days=('pm2_5','count'), pm_complete_lag_days=('pm2_5_lag10_mean','count'), cases_sum=('cases','sum'), attributed_deaths=('death_attributed','sum')).reset_index())
coverage.to_csv(OUT+'/coverage_report.csv',index=False)
diagnostics={'analysis_rows':int(len(fit)),'countries':sorted(fit.nation.unique().tolist()),'date_min':str(fit.date.min().date()),'date_max':str(fit.date.max().date()),'pm25_min':float(fit.pm2_5_lag10_mean.min()),'pm25_max':float(fit.pm2_5_lag10_mean.max()),'pm25_sd':float(fit.pm2_5_lag10_mean.std()),'outcome_definition':'Reported daily deaths shifted 8 days earlier as a transparent fixed-delay approximation; cases are daily differences of cumulative dashboard-preserved records.','model_formula':formula,'model_converged':bool(model.converged),'effect':effect}
json.dump(diagnostics,open(OUT+'/analysis_diagnostics.json','w'),indent=2)
print(json.dumps(diagnostics,indent=2))

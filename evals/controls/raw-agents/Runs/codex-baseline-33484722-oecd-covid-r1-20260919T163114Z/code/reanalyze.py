#!/usr/bin/env python3
"""Independent reconstruction of the article's adjusted day-80 case model.

Inputs are downloaded separately into ../raw.  This script makes a reproducible
country cross-section and fits OLS with all covariates printed in Table 1.
"""
from pathlib import Path
import json, hashlib
import pandas as pd
import numpy as np
import statsmodels.api as sm

OUT = Path('/output')
RAW = OUT / 'raw'
COUNTRIES = {
 'Australia':'AUS','Austria':'AUT','Belgium':'BEL','Canada':'CAN','Chile':'CHL',
 'Czechia':'CZE','Denmark':'DNK','Estonia':'EST','Finland':'FIN','France':'FRA',
 'Germany':'DEU','Greece':'GRC','Hungary':'HUN','Iceland':'ISL','Ireland':'IRL',
 'Israel':'ISR','Italy':'ITA','Japan':'JPN','Korea, South':'KOR','Latvia':'LVA',
 'Lithuania':'LTU','Luxembourg':'LUX','Mexico':'MEX','Netherlands':'NLD',
 'New Zealand':'NZL','Norway':'NOR','Poland':'POL','Portugal':'PRT','Slovakia':'SVK',
 'Slovenia':'SVN','Spain':'ESP','Sweden':'SWE','Switzerland':'CHE','Turkey':'TUR',
 'United Kingdom':'GBR','US':'USA'}

def wb(indicator):
    p = RAW / f'wb_{indicator}.json'
    d = json.loads(p.read_text())[1]
    return pd.DataFrame([{'iso3':x['countryiso3code'], 'year':int(x['date']),
                          'value':x['value']} for x in d if x['countryiso3code']])

def choose(df, preferred, fallback, max_fallback=False):
    rows=[]
    for iso in COUNTRIES.values():
        a=df[(df.iso3==iso)&(df.year==preferred)&df.value.notna()]
        if not a.empty: rows.append((iso, float(a.iloc[0].value), preferred)); continue
        b=df[(df.iso3==iso)&df.year.isin(fallback)&df.value.notna()]
        if b.empty: rows.append((iso,np.nan,np.nan))
        else:
            pick=b.loc[b.value.idxmax()] if max_fallback else b.sort_values('year',ascending=False).iloc[0]
            rows.append((iso,float(pick.value),int(pick.year)))
    return pd.DataFrame(rows,columns=['iso3','value','year'])

def outcomes():
    x=pd.read_csv(RAW/'jhu_confirmed_global.csv')
    dates=pd.to_datetime(x.columns[4:], format='%m/%d/%y')
    vals=x.iloc[:,4:].copy(); vals.columns=dates
    x['country_sum']=x['Country/Region'].replace({'Korea, South':'Korea, South','US':'US'})
    g=vals.groupby(x.country_sum).sum()
    rows=[]
    for country,iso in COUNTRIES.items():
        s=g.loc[country]
        positive=s[s>0]
        first=positive.index.min()
        target=first + pd.Timedelta(days=79) # first-positive date is counted as day 1
        rows.append({'country_jhu':country,'iso3':iso,'first_case_date':first.date().isoformat(),
          'day80_date':target.date().isoformat(),'cases_day80':float(s.get(target,np.nan)),
          'outcome_available':bool(target in s.index)})
    return pd.DataFrame(rows)

def main():
    o=outcomes()
    pm=choose(wb('pm25'),2017,[]).rename(columns={'value':'pm25_2017','year':'pm25_year'})
    exceedance=choose(wb('pm25_exceedance'),2017,[]).rename(columns={'value':'pm25_exceedance_pct_2017','year':'pm25_exceedance_year'})
    physician=choose(wb('physicians'),2017,[2016,2015],True).rename(columns={'value':'physicians_per_1000','year':'physicians_year'})
    beds=choose(wb('beds'),2015,[2014,2013,2012],True).rename(columns={'value':'beds_per_1000','year':'beds_year'})
    elderly=choose(wb('elderly'),2018,[]).rename(columns={'value':'elderly_pct_2018','year':'elderly_year'})
    density=choose(wb('density'),2019,[]).rename(columns={'value':'density_2019','year':'density_year'})
    gdp=choose(wb('gdp'),2019,[]).rename(columns={'value':'gdp_per_capita_usd_2019','year':'gdp_year'})
    population=choose(wb('population'),2019,[]).rename(columns={'value':'population_2019','year':'population_year'})
    panel=o
    for d in [pm, exceedance, physician, beds, elderly, density, gdp, population]: panel=panel.merge(d,on='iso3',how='left')
    panel['case_rate_per_10000_day80']=panel.cases_day80/panel.population_2019*10000
    panel['log_case_rate_day80']=np.log(panel.case_rate_per_10000_day80)
    panel.to_csv(OUT/'analysis_panel.csv',index=False)
    panel[['country_jhu','iso3','pm25_2017','pm25_year','pm25_exceedance_pct_2017','pm25_exceedance_year']].to_csv(OUT/'exposure_table.csv',index=False)
    vars=['elderly_pct_2018','density_2019','gdp_per_capita_usd_2019','physicians_per_1000','beds_per_1000','pm25_2017','pm25_exceedance_pct_2017']
    complete=panel.dropna(subset=['log_case_rate_day80']+vars).copy()
    fit=sm.OLS(complete.log_case_rate_day80,sm.add_constant(complete[vars]),missing='raise').fit()
    ci=fit.conf_int().loc['pm25_2017']
    summary={'n_eligible_countries':36,'n_outcome_dates_available':int(panel.outcome_available.sum()),
             'n_complete_model_rows':int(len(complete)), 'dependent_variable':'log cases per 10,000 on day 80',
             'pm25_coefficient':float(fit.params['pm25_2017']), 'pm25_ci95_low':float(ci.iloc[0]),
             'pm25_ci95_high':float(ci.iloc[1]), 'pm25_pvalue':float(fit.pvalues['pm25_2017']),
             'r_squared':float(fit.rsquared), 'covariates':vars}
    (OUT/'model_output.txt').write_text(fit.summary().as_text()+'\n\n'+json.dumps(summary,indent=2)+'\n')
    (OUT/'model_summary.json').write_text(json.dumps(summary,indent=2)+'\n')

if __name__=='__main__': main()

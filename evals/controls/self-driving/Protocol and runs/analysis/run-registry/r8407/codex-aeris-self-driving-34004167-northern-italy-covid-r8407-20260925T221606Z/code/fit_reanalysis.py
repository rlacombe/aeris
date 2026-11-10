"""Build and fit the article-aligned NO2 region-day panel from public sources."""
from pathlib import Path
import json
import pandas as pd
import statsmodels.api as sm
from statsmodels.genmod.cov_struct import Autoregressive
from statsmodels.genmod.families import Poisson

ROOT=Path('/output')
out=pd.read_csv(ROOT/'data/dpc-regioni.csv')
out['date']=pd.to_datetime(out.data).dt.date.astype(str)
out=out[out.denominazione_regione.isin(['Lombardia','Veneto'])].copy()
out=out[(out.date>='2020-02-21')&(out.date<='2020-05-19')].sort_values(['denominazione_regione','date'])
out['cases']=out.groupby('denominazione_regione').totale_casi.diff().fillna(out.totale_casi).clip(lower=0).astype(int)
out['deaths']=out.groupby('denominazione_regione').deceduti.diff().fillna(out.deceduti).clip(lower=0).astype(int)
out=out.rename(columns={'denominazione_regione':'region'})[['region','date','cases','deaths']]
daily=pd.read_csv(ROOT/'data/eea_no2_daily.csv'); daily=daily[(daily.date>='2020-02-21')&(daily.date<='2020-05-19')]
ltap=pd.read_csv(ROOT/'data/eea_no2_ltap.csv')
panel=out.merge(daily,on=['region','date'],how='left').merge(ltap[['region','ltap_no2']],on='region',how='left')
panel['lockdown']=(panel.date>='2020-02-22').astype(int)
panel['date_index']=pd.to_datetime(panel.date).map(pd.Timestamp.toordinal)
panel.to_csv(ROOT/'analysis_panel.csv',index=False)
fit=panel.dropna(subset=['stap_no2','ltap_no2']).copy()
X=sm.add_constant(fit[['stap_no2','ltap_no2','lockdown']])
models={}; estimates=[]
for outcome in ['cases','deaths']:
    # Article's log-link count GEE and AR(1) working correlation, clustered by region.
    m=sm.GEE(fit[outcome],X,groups=fit.region.to_numpy(),time=fit.date_index.to_numpy(),family=Poisson(),cov_struct=Autoregressive())
    r=m.fit()
    models[outcome]=r
    for term in ['stap_no2','ltap_no2']:
        b=float(r.params[term]); se=float(r.bse[term])
        estimates.append({'outcome':outcome,'term':term,'rate_ratio_per_1_ug_m3':float(__import__('math').exp(b)),'ci95_low':float(__import__('math').exp(b-1.96*se)),'ci95_high':float(__import__('math').exp(b+1.96*se)),'coefficient':b,'robust_se':se,'p_value':float(r.pvalues[term])})
(ROOT/'model_output.json').write_text(json.dumps({'formula':'log(E[Y]) = intercept + beta_STAP*STAP_NO2 + beta_LTAP*LTAP_NO2 + beta_LOCK*LOCKDOWN; Poisson GEE, AR(1) working correlation, cluster=region','n_rows':len(fit),'estimates':estimates},indent=2))
pd.DataFrame(estimates).to_csv(ROOT/'model_estimates.csv',index=False)
with open(ROOT/'model_output.txt','w') as f:
    for name,r in models.items(): f.write('\n### '+name+'\n'+r.summary().as_text()+'\n')
coverage=(panel.groupby('region').agg(eligible_days=('date','size'),included_days=('stap_no2',lambda x:int(x.notna().sum())),mean_stations=('n_stations','mean'),ltap=('ltap_no2','first')).reset_index())
coverage.to_csv(ROOT/'coverage_diagnostics.csv',index=False)

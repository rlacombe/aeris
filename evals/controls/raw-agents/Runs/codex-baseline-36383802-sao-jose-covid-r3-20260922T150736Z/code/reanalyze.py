#!/usr/bin/env python3
"""Independent reanalysis of PMID 36383802.

Inputs:
* SIH-RD public re-release of official DATASUS microdata, queried by month
  from the documented S3 partition layout. Credentials are intentionally read
  only from environment variables (they are published by the data host; never
  write them to an artifact).
* Open-Meteo historical air-quality API, retrieved as raw JSON.

The SIH source is inspected only after sanitization: every field other than
MUNIC_RES, DIAG_PRINC and DT_INTER is dropped before any filtering/modeling.
"""
import os, json, hashlib, sys
from pathlib import Path
import pandas as pd
import numpy as np
import statsmodels.api as sm
import pyarrow.dataset as pds
import pyarrow.fs as fs

OUT=Path('/output'); RAW=OUT/'raw'; LOG=OUT/'logs'
OUT.mkdir(exist_ok=True); RAW.mkdir(exist_ok=True); LOG.mkdir(exist_ok=True)
KEEP=['MUNIC_RES','DIAG_PRINC','DT_INTER']

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def get_outcome():
    """Retrieve and sanitize 13 DATASUS-derived monthly partitions."""
    key=os.environ['HEALTHBR_ACCESS_KEY']; secret=os.environ['HEALTHBR_SECRET_KEY']
    s3=fs.S3FileSystem(endpoint_override='https://5c499208eebced4e34bd98ffa204f2fb.r2.cloudflarestorage.com', access_key=key, secret_key=secret, region='auto')
    dates=pd.date_range('2020-04-01','2021-04-01',freq='MS')
    all_rows=[]; audit=[]
    for d in dates:
        path=f'healthbr-data/sih/rd/ano={d.year}/mes={d.month:02d}/uf=SP/'
        ds=pds.dataset(path,filesystem=s3,format='parquet')
        cols=ds.schema.names
        dropped=[x for x in cols if x not in KEEP]
        # Read only retained fields: prevents exposure, fitted values, and all
        # nonessential health fields from entering the local workflow.
        tab=ds.to_table(columns=KEEP)
        z=tab.to_pandas()
        audit.append({'partition':path,'source_columns':cols,'retained_columns':KEEP,'dropped_columns':dropped,'rows_before_filter':len(z)})
        z=z[(z.MUNIC_RES.astype(str).str.strip()=='354990') & (z.DIAG_PRINC.astype(str).str.strip()=='B342')]
        all_rows.append(z)
    pd.DataFrame(audit).to_json(OUT/'sanitization_audit.json',orient='records',indent=2)
    z=pd.concat(all_rows,ignore_index=True)
    z['date']=pd.to_datetime(z.DT_INTER,format='%Y%m%d',errors='coerce')
    z=z[(z.date>='2020-04-01') & (z.date<='2021-04-30')]
    z.to_csv(OUT/'sanitized_outcome_records.csv',index=False)
    daily=pd.DataFrame({'date':pd.date_range('2020-04-01','2021-04-30',freq='D')})
    daily=daily.merge(z.groupby('date').size().rename('admissions'),on='date',how='left').fillna({'admissions':0})
    daily.admissions=daily.admissions.astype(int)
    daily.to_csv(OUT/'outcome_daily.csv',index=False)
    return daily, len(z)

def exposure():
    q=json.loads((RAW/'openmeteo_hourly.json').read_text())['hourly']
    h=pd.DataFrame(q); h['time']=pd.to_datetime(h['time'])
    h['date']=h.time.dt.normalize()
    # Same-day arithmetic mean across the 24 hourly values. API returns ug/m3
    # for pollutants, Celsius and percent RH; no author pollution data used.
    e=h.groupby('date',as_index=False)[['ozone','nitrogen_dioxide','pm10']].mean()
    # Historical weather is a separate Open-Meteo endpoint; air-quality
    # responses do not supply these weather variables for this period.
    w=pd.DataFrame(json.loads((RAW/'openmeteo_weather.json').read_text())['hourly'])
    w['time']=pd.to_datetime(w['time']); w['date']=w.time.dt.normalize()
    w=w.groupby('date',as_index=False)[['temperature_2m','relative_humidity_2m']].mean()
    e=e.merge(w,on='date',how='left')
    e=e.rename(columns={'ozone':'o3','nitrogen_dioxide':'no2','temperature_2m':'temp','relative_humidity_2m':'rh'})
    e.to_csv(OUT/'exposure_daily.csv',index=False)
    return e

def fit(daily,e):
    panel=daily.merge(e,on='date',how='left')
    panel['dow']=panel.date.dt.dayofweek.astype('category'); panel['calendar_day']=(panel.date-panel.date.min()).dt.days+1
    # Lagged exposure availability requires preceding seven days; outcome period is never relaxed.
    for v in ['o3','no2','pm10']:
        for lag in range(8): panel[f'{v}_lag{lag}']=panel[v].shift(lag)
    panel.to_csv(OUT/'analysis_panel_untrimmed.csv',index=False)
    if panel[['o3','no2','pm10']].notna().sum().min() == 0:
        panel.to_csv(OUT/'analysis_panel.csv',index=False)
        pd.DataFrame(columns=['pollutant','lag_days','native_beta_per_ug_m3','native_ci_low','native_ci_high','rr_per_10ug_m3','rr_ci_low','rr_ci_high','n_days','model']).to_csv(OUT/'model_output.csv',index=False)
        (OUT/'model_summary.txt').write_text('NO MODEL FIT: Open-Meteo historical air-quality response contains no non-missing pollutant values for 2020-03-25 through 2021-04-30.\n')
        return None,panel
    panel=panel[panel[[f'{v}_lag7' for v in ['o3','no2','pm10']]+['temp','rh']].notna().all(axis=1)].copy()
    panel.to_csv(OUT/'analysis_panel.csv',index=False)
    rows=[]
    for lag in range(8):
        terms=[f'o3_lag{lag}',f'no2_lag{lag}',f'pm10_lag{lag}','temp','rh','calendar_day']
        X=pd.get_dummies(panel[terms+['dow']],columns=['dow'],drop_first=True,dtype=float)
        X=sm.add_constant(X,has_constant='add')
        X=X.astype(float)
        # NB2 GLM with default alpha=1; article did not report dispersion.
        mod=sm.GLM(panel.admissions.astype(float),X,family=sm.families.NegativeBinomial()).fit()
        for v,label in [('o3','O3'),('no2','NO2'),('pm10','PM10')]:
            term=f'{v}_lag{lag}'; b=float(mod.params[term]); se=float(mod.bse[term]); lo=b-1.96*se; hi=b+1.96*se
            rows.append({'pollutant':label,'lag_days':lag,'native_beta_per_ug_m3':b,'native_ci_low':lo,'native_ci_high':hi,'rr_per_10ug_m3':float(np.exp(10*b)),'rr_ci_low':float(np.exp(10*lo)),'rr_ci_high':float(np.exp(10*hi)),'n_days':int(len(panel)),'model':'NB2 GLM log link; O3, NO2, PM10 at common lag; temperature, RH, day-of-week indicators, linear calendar day'})
    result=pd.DataFrame(rows); result.to_csv(OUT/'model_output.csv',index=False)
    (OUT/'model_summary.txt').write_text('All 8 fitted model summaries are represented by coefficient rows in model_output.csv.\n'+result.to_string(index=False)+'\n')
    return result,panel

if __name__=='__main__':
    daily,n=get_outcome()
    e=exposure()
    r,p=fit(daily,e)
    (OUT/'run_metrics.json').write_text(json.dumps({'status':'completed_blocker' if r is None else 'completed_fit','outcome_records':n,'outcome_days':len(daily),'model_days':len(p),'raw_openmeteo_sha256':sha(RAW/'openmeteo_hourly.json'),'reason':None if r is not None else 'No usable independent pollutant exposure values in retrieved historical response'},indent=2))

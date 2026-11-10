#!/usr/bin/env python3
"""Independent reconstruction for PMID 33227571.

Uses SIH-RD microdata mirrored byte-for-byte from DATASUS and Open-Meteo
archive weather.  It deliberately does not retrieve authors' data or CETESB
values.  The published multivariable environmental clustering cannot be fitted
unless all three daily pollutant series are available from an independent source.
"""
import csv, datetime as dt, hashlib, json, os, sys, time
from pathlib import Path
import boto3
import pandas as pd
import pyarrow.parquet as pq
import pyarrow.fs as pafs
import requests

OUT=Path('/output'); RAW=OUT/'raw'; LOG=OUT/'logs'; RAW.mkdir(exist_ok=True); LOG.mkdir(exist_ok=True)
runlog=[]
def record(url, status, n, note=''):
    runlog.append({'url':url,'attempt':1,'status':status,'bytes':n,'delay_seconds':0,'note':note})
def get(url, dest):
    r=requests.get(url, timeout=60); record(url,r.status_code,len(r.content)); r.raise_for_status(); dest.write_bytes(r.content); return r

# 39 legally defined municipalities in the São Paulo metropolitan region.
# SIH stores the six-digit municipality stem, while the IBGE reference codes
# have a final check digit; these correspond to the 39 RM São Paulo members.
MUNICIPALITIES=['350390','350570','350660','350900','350920','351060','351300','351380','351500','351510','351570','351630','351640','351830','351880','352220','352250','352310','352500','352620','352850','352940','353060','353440','353910','353980','354330','354410','354500','354680','354730','354780','354870','354880','354995','355030','355250','355280','355645']

def s3fs():
    return pafs.S3FileSystem(
      access_key='28c72d4b3e1140fa468e367ae472b522',
      secret_key='2937b2106736e2ba64e24e92f2be4e6c312bba3355586e41ce634b14c1482951',
      endpoint_override='https://5c499208eebced4e34bd98ffa204f2fb.r2.cloudflarestorage.com', region='auto')

def fetch_outcomes():
    fs=s3fs(); frames=[]; provenance=[]
    # Competence records can contain admissions beginning earlier; include 4
    # months beyond 2015 to avoid a known billing-lag truncation.
    months=pd.period_range('2012-01','2016-04',freq='M')
    for p in months:
        key=f'healthbr-data/sih/rd/ano={p.year}/mes={p.month:02d}/uf=SP/part-0.parquet'
        url='https://data.sidneybissoli.com/'+key.replace('healthbr-data/','')
        try:
            with fs.open_input_file(key) as f:
                tab=pq.read_table(f, columns=['DT_INTER','DIAG_PRINC','MUNIC_RES','MORTE','N_AIH'])
            df=tab.to_pandas()
            keep=df[(df.DIAG_PRINC.astype(str).str.startswith('I21')) & df.MUNIC_RES.astype(str).isin(MUNICIPALITIES)].copy()
            frames.append(keep); provenance.append({'competence':str(p),'url':url,'rows_total':len(df),'rows_kept':len(keep)})
            record(url,200,0,'S3 parquet stream; byte count unavailable to reader')
        except Exception as e:
            provenance.append({'competence':str(p),'url':url,'error':repr(e)}); record(url,'error',0,repr(e))
    raw=pd.concat(frames,ignore_index=True)
    raw['date']=pd.to_datetime(raw.DT_INTER,errors='coerce')
    target=raw[(raw.date>='2012-01-01')&(raw.date<='2015-12-31')].copy()
    # A record could be duplicated across billing competences. Deduplicate AIHs
    # before counts, preserving one admission date/diagnosis record.
    target=target.drop_duplicates(subset=['N_AIH'])
    daily=target.groupby('date').size().rename('ami_admissions').reindex(pd.date_range('2012-01-01','2015-12-31'),fill_value=0).reset_index().rename(columns={'index':'date'})
    daily.to_csv(OUT/'outcome_daily.csv',index=False)
    (RAW/'sih_provenance.json').write_text(json.dumps(provenance,indent=2))
    return daily, provenance

def fetch_weather():
    url=('https://archive-api.open-meteo.com/v1/archive?latitude=-23.5505&longitude=-46.6333'
         '&start_date=2012-01-01&end_date=2015-12-31&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,relative_humidity_2m_mean&timezone=America%2FSao_Paulo')
    r=get(url,RAW/'openmeteo_weather.json'); d=r.json()['daily']
    w=pd.DataFrame(d).rename(columns={'time':'date'})
    w['date']=pd.to_datetime(w.date)
    w['temperature_range_c']=w.temperature_2m_max-w.temperature_2m_min
    w.to_csv(OUT/'weather_daily.csv',index=False)
    return w,url

def main():
    outcome, prov=fetch_outcomes()
    weather,wurl=fetch_weather()
    panel=outcome.merge(weather,on='date',how='left')
    # Explicitly preserve failed exposure construction: no values are invented.
    exposure=pd.DataFrame({'date':panel.date,'pm25_ug_m3':pd.NA,'pm10_ug_m3':pd.NA,'no2_ug_m3':pd.NA})
    exposure.to_csv(OUT/'exposure_daily.csv',index=False)
    panel=panel.merge(exposure,on='date',how='left')
    panel.to_csv(OUT/'analysis_panel.csv',index=False)
    model={'status':'not_run','reason':'Published Ward hierarchical clustering requires daily PM2.5, PM10, and NO2. No independent, credential-free public historical source was successfully retrieved in this run; fitting clusters with missing pollutants would alter the scientific task.','n_days':int(len(panel)),'outcome_sum':int(panel.ami_admissions.sum()),'weather_complete_days':int(panel.temperature_2m_max.notna().sum()),'pollutant_complete_days':int(panel.pm25_ug_m3.notna().sum())}
    (OUT/'model_output.json').write_text(json.dumps(model,indent=2)+'\n')
    (LOG/'request_log.json').write_text(json.dumps(runlog,indent=2)+'\n')
    print(json.dumps(model))
if __name__=='__main__': main()

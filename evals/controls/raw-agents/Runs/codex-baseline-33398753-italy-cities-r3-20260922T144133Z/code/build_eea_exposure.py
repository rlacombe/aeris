#!/usr/bin/env python3
"""Construct independent 2018 PM10 exposure from EEA validated station data.

Assignment locked before inspection: geocode provincial capital via Nominatim;
nearest Italian EEA station offering PM10 within 25 km; count local-calendar-date
daily means >50 ug/m3, retaining a city only if >=75% of 2018 dates have a mean.
"""
import csv,json,re,time,hashlib,math,os
from pathlib import Path
from urllib.parse import urlencode
import pandas as pd
import requests

ROOT=Path('/output'); RAW=ROOT/'raw'; DER=ROOT/'derived'; LOG=ROOT/'logs'
reqlog=[]
def get(url, path, label, headers=None):
    for attempt in range(1,7):
        try:
            x=requests.get(url,headers=headers or {'User-Agent':'independent-reanalysis/1.0'},timeout=(5,12))
            x.raise_for_status(); b=x.content; status=x.status_code
            path.write_bytes(b); reqlog.append({'label':label,'url':url,'attempt':attempt,'status':status,'bytes':len(b),'delay_s':0}); return b
        except Exception as e:
            delay=[5,15,45,120,300][min(attempt-1,4)]
            reqlog.append({'label':label,'url':url,'attempt':attempt,'status':'error','bytes':0,'delay_s':delay,'error':str(e)})
            if attempt==6: raise
            time.sleep(delay)

# Inputs whose inspection was permitted only after sanitization.
cities=list(csv.DictReader(open(DER/'author_sanitized.csv')))
stations=json.load(open(RAW/'eea_italy_stations.geojson'))['features']
def hav(a,b,c,d):
    R=6371; p=math.pi/180; x=(c-a)*p; y=(d-b)*p
    q=math.sin(y/2)**2+math.cos(b*p)*math.cos(d*p)*math.sin(x/2)**2
    return 2*R*math.asin(math.sqrt(q))
def pmurl(feature):
    urls=re.findall(r'href="([^"]+\.parquet)"[^>]*>PM10',feature['properties']['PopupInfo'])
    return urls[0] if urls else None
stations=[s for s in stations if pmurl(s)]
out=[]
checkpoint=DER/'eea_pm10_exposure.csv'
done=set()
if checkpoint.exists():
    out=pd.read_csv(checkpoint).fillna('').to_dict('records'); done={str(r['city']) for r in out}
for n,row in enumerate(cities,1):
    city=row['Italian Province Capital'].strip()
    if city in done: continue
    # Nominatim policy-compatible serial request (>=1.1 seconds between calls).
    u='https://nominatim.openstreetmap.org/search?'+urlencode({'q':city+', Italy','format':'jsonv2','limit':1})
    geo=json.loads(get(u,RAW/f'geocode_{n:02d}.json','geocode').decode())
    time.sleep(1.1)
    if not geo:
        out.append({'city':city,'assignment_status':'no_geocode'}); pd.DataFrame(out).to_csv(checkpoint,index=False); continue
    lon,lat=float(geo[0]['lon']),float(geo[0]['lat'])
    cand=[]
    for s in stations:
        slon,slat=s['geometry']['coordinates']; dist=hav(lon,lat,slon,slat)
        cand.append((dist,s))
    dist,s=min(cand,key=lambda x:x[0]); url=pmurl(s)
    base={'city':city,'city_lon':lon,'city_lat':lat,'station_code':s['properties']['AirQualityStationEoICode'],'station_name':s['properties']['AQStationName'],'station_distance_km':round(dist,3),'eea_pm10_url':url}
    if dist>25:
        out.append(base|{'assignment_status':'nearest_station_over_25km'}); pd.DataFrame(out).to_csv(checkpoint,index=False); continue
    p=RAW/f"pm10_{s['properties']['AirQualityStationEoICode']}.parquet"
    if not p.exists(): get(url,p,'eea_pm10')
    try:
        df=pd.read_parquet(p)
        # EEA parquet schema has UTC datetime and concentration/value field; resolve defensibly.
        dates=[c for c in df.columns if any(z in c.lower() for z in ['datetime','date','time'])]
        vals=[c for c in df.columns if c.lower() in ['value','concentration','measurementvalue'] or 'concentration' in c.lower()]
        if not dates or not vals: raise ValueError('unrecognized EEA parquet columns: '+repr(list(df.columns)))
        d=df[[dates[0],vals[0]]].rename(columns={dates[0]:'timestamp',vals[0]:'value'})
        d['timestamp']=pd.to_datetime(d.timestamp,utc=True,errors='coerce').dt.tz_convert('Europe/Rome')
        d['value']=pd.to_numeric(d.value,errors='coerce')
        d=d[(d.timestamp>='2018-01-01')&(d.timestamp<'2019-01-01')].dropna()
        daily=d.set_index('timestamp').value.resample('D').mean()
        valid=int(daily.notna().sum()); exceed=int((daily>50).sum())
        status='included' if valid>=274 else 'insufficient_daily_coverage'
        out.append(base|{'assignment_status':status,'valid_daily_means_2018':valid,'pm10_days_over_50':exceed})
    except Exception as e: out.append(base|{'assignment_status':'processing_error','error':str(e)})
    pd.DataFrame(out).to_csv(checkpoint,index=False)
pd.DataFrame(out).to_csv(DER/'eea_pm10_exposure.csv',index=False)
json.dump(reqlog,open(LOG/'request_log.json','w'),indent=2)

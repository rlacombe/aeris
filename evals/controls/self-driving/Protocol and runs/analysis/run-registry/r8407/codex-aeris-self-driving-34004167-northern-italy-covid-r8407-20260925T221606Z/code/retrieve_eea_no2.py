"""Recover article-named EEA validated NO2 observations for the two regions."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import csv, json, re, urllib.request
import pandas as pd
from shapely.geometry import shape, Point

ROOT=Path('/output')
urls=(ROOT/'evidence/eea-urls3.txt').read_text(encoding='utf-8-sig').splitlines()[1:]
regions=json.load(open(ROOT/'data/italy-adm2.geojson'))['features']
regions={f['properties']['shapeName']:shape(f['geometry']) for f in regions if f['properties']['shapeName'] in {'Lombardia','Veneto'}}
stations=json.load(open(ROOT/'data/eea-italy-stations.geojson'))['features']
station_region={}
for s in stations:
    pt=Point(s['geometry']['coordinates'])
    for region, poly in regions.items():
        if poly.covers(pt): station_region[s['properties']['AirQualityStationEoICode']]=region
by_code={}
for u in urls:
    m=re.search(r'SPO\.(IT\d+A)_8_',u)
    if m and m.group(1) in station_region: by_code[m.group(1)]=u
outdir=ROOT/'data/eea_no2_parquet'; outdir.mkdir(exist_ok=True)
def get(item):
    code,url=item; dest=outdir/(code+'.parquet')
    if not dest.exists(): urllib.request.urlretrieve(url,dest)
    return code,str(dest.stat().st_size)
with ThreadPoolExecutor(max_workers=6) as ex:
    results=list(ex.map(get,by_code.items()))
(ROOT/'evidence/eea-selected-stations.json').write_text(json.dumps({'station_region':station_region,'selected_urls':by_code,'downloads':results},indent=2))
rows=[]
for code in by_code:
    df=pd.read_parquet(outdir/(code+'.parquet'))
    df.columns=[str(c) for c in df.columns]
    # Files use time/value fields; retain raw schema in manifest for reproducibility.
    candidates=[c for c in df.columns if c.lower() in {'datetimebegin','datetime','date','date_time','starttime','datetimestart','start'}]
    vals=[c for c in df.columns if c.lower() in {'value','concentration','value_numeric'}]
    if not candidates or not vals: continue
    z=pd.DataFrame({'datetime':pd.to_datetime(df[candidates[0]],utc=True,errors='coerce'), 'value':pd.to_numeric(df[vals[0]],errors='coerce')})
    if 'Validity' in df.columns:
        z=z[pd.to_numeric(df['Validity'], errors='coerce').to_numpy() > 0]
    z['date']=z.datetime.dt.date.astype(str); z['station_code']=code; z['region']=station_region[code]
    z=z[(z.date>='2013-01-01')&(z.date<='2020-05-19') & z.value.notna() & (z.value >= 0)]
    rows.append(z[['date','region','station_code','value']])
raw=pd.concat(rows,ignore_index=True)
raw.to_csv(ROOT/'data/eea_no2_raw.csv',index=False)
# An observation may be hourly or daily; mean per station-day first, then equal-weight station mean.
station_day=raw.groupby(['region','station_code','date'],as_index=False).value.mean()
daily=station_day.groupby(['region','date'],as_index=False).agg(stap_no2=('value','mean'),n_stations=('station_code','nunique'))
daily.to_csv(ROOT/'data/eea_no2_daily.csv',index=False)
ltap=station_day.groupby('region',as_index=False).agg(ltap_no2=('value','mean'),n_station_days=('value','size'),first_date=('date','min'),last_date=('date','max'))
ltap.to_csv(ROOT/'data/eea_no2_ltap.csv',index=False)

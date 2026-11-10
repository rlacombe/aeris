#!/usr/bin/env python3
"""Independent public-data reconstruction of PMC7781409.

Inputs are fetched separately before this script.  No author-derived analytic
data are read.  The EEA station service supplies PM10 measurements; Italian
Civil Protection supplies province-level cumulative confirmed cases; Istat
supplies population, and GISCO NUTS3 geometries supply land area.
"""
import json, re, os, hashlib, math, glob
from pathlib import Path
import pandas as pd
import numpy as np
import requests
import statsmodels.api as sm
from pyproj import Transformer
from scipy.spatial.distance import cdist

OUT=Path('/output'); RAW=OUT/'raw'; LOG=OUT/'logs'
for x in [OUT,RAW,LOG]: x.mkdir(exist_ok=True,parents=True)
session=requests.Session()

def retrieve(url, path):
    # One request: failures are evidence, not silently retried.
    r=session.get(url,timeout=120)
    (LOG/(path.name+'.http.json')).write_text(json.dumps({'url':url,'status':r.status_code,'bytes':len(r.content)}))
    r.raise_for_status(); path.write_bytes(r.content)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

stations=json.load(open(RAW/'eea_italy_stations.json'))['features']
rows=[]
for f in stations:
    html=f['properties'].get('PopupInfo','')
    m=re.search(r'href="([^"]+\.parquet)"[^>]*>PM10</a>',html)
    if m:
        lon,lat=f['geometry']['coordinates']; rows.append({'station':f['properties']['AirQualityStationEoICode'],'station_name':f['properties']['AQStationName'],'lon':lon,'lat':lat,'pm10_url':m.group(1)})
st=pd.DataFrame(rows)

# Provincial Civil Protection records include a capital coordinate.  The unit is
# necessarily province (official archive does not publish municipality cases),
# recorded as a disclosed geographic substitution.
dpc=pd.read_csv(RAW/'dpc_province.csv',encoding='utf-8-sig')
dpc['date']=pd.to_datetime(dpc['data']).dt.date.astype(str)
dpc['prov_code']=dpc['codice_provincia'].astype(str).str.zfill(3)
dpc=dpc[(dpc.codice_provincia.notna())&(dpc.codice_provincia!=0)]
# NUTS fields were added later to this longitudinal archive.  Select the most
# recent record for each province so that its current archive metadata is used.
caps=dpc.sort_values('data',ascending=False)[['prov_code','denominazione_provincia','lat','long','codice_nuts_3']].drop_duplicates('prov_code').copy()
caps=caps.dropna(subset=['lat','long','codice_nuts_3'])

# Great-circle-ish nearest (coordinates sufficiently local for ranking).
a=caps[['lat','long']].to_numpy(); b=st[['lat','lon']].to_numpy()
idx=cdist(a,b).argmin(axis=1)
chosen=st.iloc[idx].reset_index(drop=True)
caps=caps.reset_index(drop=True).join(chosen.add_prefix('eea_'))
caps['station_distance_degrees']=cdist(a,b).min(axis=1)
# The station map's legacy E1a URLs returned 404.  The current EEA download
# API was queried once with the identical public request (Italy, PM10, daily,
# 2018) and its returned URL list is used here.  This is a transport/source
# recovery, not a scientific change.
url_lines=pd.read_csv(RAW/'eea_pm10_2018_urls.csv',encoding='utf-8-sig')['ParquetFileUrl'].dropna().tolist()
url_by_station={re.search(r'SPO\.(IT[A-Z0-9]+)_',u).group(1):u for u in url_lines if re.search(r'SPO\.(IT[A-Z0-9]+)_',u)}
caps['eea_pm10_url']=caps['eea_station'].map(url_by_station)
caps=caps.dropna(subset=['eea_pm10_url']).copy()
caps.to_csv(OUT/'station_assignment.csv',index=False)

# Retrieve unique closest-station files.  Each is immutable public EEA E1a
# parquet; inspect schema defensively because providers have changed it.
for url, station in caps[['eea_pm10_url','eea_station']].drop_duplicates().itertuples(index=False):
    dest=RAW/f'pm10_{station}.parquet'
    if not dest.exists(): retrieve(url,dest)

def pm10_exceedance(station):
    p=RAW/f'pm10_{station}.parquet'
    z=pd.read_parquet(p)
    z.columns=[str(c) for c in z.columns]
    # EEA parquet uses DatetimeBegin/DatetimeEnd and Concentration.  Aggregate
    # subdaily readings to daily maxima, then count days > 50 ug/m3 in 2018.
    timecol=next((c for c in z if c.lower() in ['datetimebegin','datetime','date','samplingpointdatetimebegin','start']),None)
    valcol=next((c for c in z if c.lower() in ['concentration','value','measurementvalue']),None)
    if timecol is None or valcol is None: raise ValueError(f'Unexpected EEA fields {z.columns.tolist()}')
    z['_date']=pd.to_datetime(z[timecol],utc=True,errors='coerce').dt.date.astype(str)
    z['_value']=pd.to_numeric(z[valcol],errors='coerce')
    z=z[z['_date'].str.startswith('2018',na=False)].dropna(subset=['_value'])
    daily=z.groupby('_date')['_value'].max()
    return pd.Series({'pm10_days_gt50':int((daily>50).sum()),'pm10_observed_days':int(daily.size),'pm10_source_rows':int(len(z))})

ex=caps[['prov_code','denominazione_provincia','eea_station','eea_station_name','station_distance_degrees']].copy()
vals=[]
for station in ex.eea_station:
    try: vals.append(pm10_exceedance(station))
    except Exception as e: vals.append(pd.Series({'pm10_days_gt50':np.nan,'pm10_observed_days':np.nan,'pm10_source_rows':np.nan,'exposure_error':str(e)}))
ex=pd.concat([ex,pd.DataFrame(vals)],axis=1)
ex.to_csv(OUT/'exposure_table.csv',index=False)

# Province population Jan 2019 from Istat SDMX bulk. Geographic area is
# calculated from public GISCO NUTS3 polygons in EPSG:3035.
pop=pd.read_csv(RAW/'istat_pop.csv',dtype={'REF_AREA':str},low_memory=False)
pop=pop[(pop.TIME_PERIOD==2019)&(pop.DATA_TYPE=='JAN')&(pop.SEX.astype(str)=='9')&(pop.AGE.astype(str)=='TOTAL')&(pop.MARITAL_STATUS.astype(str)=='99')]
# Istat uses NUTS3 identifiers (five characters) for its province aggregate;
# municipality identifiers are six-digit numeric strings.
pop=pop[pop.REF_AREA.str.len()==5][['REF_AREA','OBS_VALUE']].rename(columns={'REF_AREA':'nuts3','OBS_VALUE':'population_2019'})
geo=json.load(open(RAW/'nuts3.geojson'))
from shapely.geometry import shape
transformer=Transformer.from_crs('EPSG:4326','EPSG:3035',always_xy=True)
from shapely.ops import transform
areas=[]
for f in geo['features']:
    nuts=f['properties'].get('NUTS_ID')
    if nuts:
        areas.append({'nuts3':nuts,'area_km2':transform(transformer.transform,shape(f['geometry'])).area/1e6})
areas=pd.DataFrame(areas)

casewide=dpc[dpc.date.isin(['2020-03-17','2020-04-07','2020-04-27'])].pivot_table(index='prov_code',columns='date',values='totale_casi',aggfunc='first').reset_index()
casewide=casewide.rename(columns={'2020-03-17':'cases_2020_03_17','2020-04-07':'cases_2020_04_07','2020-04-27':'cases_2020_04_27'})
panel=caps.merge(ex[['prov_code','pm10_days_gt50','pm10_observed_days']],on='prov_code').merge(casewide,on='prov_code').merge(pop,left_on='codice_nuts_3',right_on='nuts3').merge(areas,left_on='codice_nuts_3',right_on='nuts3',how='left',suffixes=('_pop','_area'))
panel['density_province_2019']=panel.population_2019/panel.area_km2
for c in ['pm10_days_gt50','density_province_2019','cases_2020_03_17','cases_2020_04_07','cases_2020_04_27']: panel['log_'+c]=np.log(panel[c].where(panel[c]>0))
panel.to_csv(OUT/'analysis_panel.csv',index=False)
# Locked comparisons: all 3 named case dates. Primary is 17 March (model 1).
results=[]
for datecol in ['cases_2020_03_17','cases_2020_04_07','cases_2020_04_27']:
    d=panel.dropna(subset=['log_'+datecol,'log_pm10_days_gt50','log_density_province_2019']).copy()
    X=sm.add_constant(d[['log_pm10_days_gt50','log_density_province_2019']]); m=sm.OLS(d['log_'+datecol],X).fit()
    ci=m.conf_int().loc['log_pm10_days_gt50']
    beta=m.params['log_pm10_days_gt50']
    # Ratio for a doubling of PM10 exceedance days: exp(beta*ln 2).
    results.append({'outcome_date':datecol.replace('cases_','').replace('_','-'),'n':int(m.nobs),'native_coefficient_loglog':beta,'ci_low_native':ci.iloc[0],'ci_high_native':ci.iloc[1],'p_value':m.pvalues['log_pm10_days_gt50'],'ratio_for_doubling_pm10_days':math.exp(beta*math.log(2)),'ratio_ci_low':math.exp(ci.iloc[0]*math.log(2)),'ratio_ci_high':math.exp(ci.iloc[1]*math.log(2)),'r_squared':m.rsquared})
    (OUT/f'model_{datecol}.txt').write_text(m.summary().as_text())
pd.DataFrame(results).to_csv(OUT/'model_output.csv',index=False)

manifest=[]
for role,path,url in [
 ('health_outcome',RAW/'dpc_province.csv','https://raw.githubusercontent.com/pcm-dpc/COVID-19/master/dati-province/dpc-covid19-ita-province.csv'),
 ('exposure_station_index',RAW/'eea_italy_stations.json','https://air.discomap.eea.europa.eu/arcgis/rest/services/AirQuality/AirQualityDownloadServiceEUMonitoringStations/MapServer/0/query?where=CountryCode%3D%27IT%27&outFields=*&returnGeometry=true&f=geojson'),
 ('exposure_download_url_list',RAW/'eea_pm10_2018_urls.csv','https://eeadmz1-downloads-api-appservice.azurewebsites.net/ParquetFile/urls (POST: IT, PM10, daily, verified/E1a, 2018-01-01..2018-12-31)'),
 ('covariate_population',RAW/'istat_pop.csv','https://esploradati.istat.it/SDMXWS/rest/data/IT1,22_289?format=csvfile'),
 ('covariate_area',RAW/'nuts3.geojson','https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_01M_2021_4326_LEVL_3.geojson')]:
    manifest.append({'role':role,'url':url,'retrieved':path.exists(),'sha256':sha(path) if path.exists() else None})
for p in sorted(RAW.glob('pm10_*.parquet')): manifest.append({'role':'exposure_measurement','url':'EEA URL recorded in station_assignment.csv','retrieved':True,'sha256':sha(p),'local_file':str(p)})
(OUT/'source_manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps(results,indent=2))

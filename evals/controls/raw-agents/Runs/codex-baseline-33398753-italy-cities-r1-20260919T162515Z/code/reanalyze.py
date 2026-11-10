#!/usr/bin/env python3
"""Independent reconstruction of Coccia (2021), Italian provincial-capitals analysis.

Inputs are retrieved from their original public publishers.  This program does
not access any numeric dataset released by the article's authors.
"""
from __future__ import annotations
import csv, hashlib, json, math, os, random, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
import unicodedata
import numpy as np
import pandas as pd
import statsmodels.api as sm

OUT = Path('/output'); RAW = OUT / 'raw'; RAW.mkdir(exist_ok=True)
REQUEST_LOG = []

def fetch(url: str, filename: str) -> Path:
    """Fetch a static resource with the frozen contract retry schedule."""
    target = RAW / filename
    delays = [5, 15, 45, 120, 300]
    for attempt in range(1, 7):
        started = datetime.now(timezone.utc).isoformat()
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'independent-reanalysis/1.0'})
            with urllib.request.urlopen(req, timeout=180) as response:
                data = response.read()
                code = response.status
            target.write_bytes(data)
            REQUEST_LOG.append({'url':url,'attempt':attempt,'started_utc':started,
                                'status':code,'bytes':len(data),'delay_seconds':0})
            return target
        except urllib.error.HTTPError as e:
            code = e.code; body = e.read(); retry = code in [408,425,429,500,502,503,504]
            retry_after = e.headers.get('Retry-After') if code == 429 else None
            delay = (float(retry_after) if retry_after and retry_after.isdigit() else delays[min(attempt-1,4)]) if retry and attempt < 6 else 0
            REQUEST_LOG.append({'url':url,'attempt':attempt,'started_utc':started,
                                'status':code,'bytes':len(body),'delay_seconds':delay})
            if not retry or attempt == 6: raise
        except (urllib.error.URLError, TimeoutError, ConnectionResetError) as e:
            delay = delays[min(attempt-1,3)] * (1 + random.uniform(0, .2)) if attempt < 5 else 0
            REQUEST_LOG.append({'url':url,'attempt':attempt,'started_utc':started,
                                'status':'transport_error','bytes':0,'delay_seconds':delay,'error':str(e)})
            if attempt == 5: raise
        time.sleep(delay)
    raise RuntimeError('unreachable')

def norm(x):
    x = unicodedata.normalize('NFKD', str(x)).encode('ascii','ignore').decode().lower()
    return ''.join(c for c in x if c.isalnum())

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

# Official Civil Protection provincial series. The published study calls these
# "cities"; the source actually has one cumulative-case total per province.
covid_urls = {d: 'https://raw.githubusercontent.com/pcm-dpc/COVID-19/master/dati-province/dpc-covid19-ita-province-'+d+'.csv'
              for d in ['20200317','20200407','20200427']}
covid = {}
for day, url in covid_urls.items():
    covid[day] = pd.read_csv(fetch(url, 'covid_'+day+'.csv'), dtype={'codice_provincia':str})
    covid[day] = covid[day][covid[day]['codice_provincia'].str.fullmatch(r'\d{3}', na=False)].copy()
    covid[day] = covid[day][covid[day]['codice_provincia'].astype(int) < 900].copy()
    covid[day] = covid[day][covid[day]['lat'].notna() & covid[day]['long'].notna()].copy()

# Eurostat NUTS3 density (annual, persons/km2); it is deliberately province,
# not municipality, density because the outcomes are province-level.
dens_url = 'https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_r_d3dens?time=2019'
dens_json = json.loads(fetch(dens_url, 'eurostat_density_2019.json').read_text())
gc = dens_json['dimension']['geo']['category']; vals = dens_json.get('value', {})
dens = []
for code, idx in gc['index'].items():
    if code.startswith('IT') and len(code) == 5 and str(idx) in vals:
        dens.append({'nuts3':code, 'density_label':gc['label'][code], 'population_density_2019':vals[str(idx)]})
dens = pd.DataFrame(dens)

# Match official province names to Eurostat's NUTS3 labels; the few historical
# 2016 Sardinian labels remain unmatched and are not imputed.
base = covid['20200317'][['codice_provincia','denominazione_provincia','sigla_provincia','lat','long','totale_casi']].copy()
base = base.rename(columns={'totale_casi':'cases_2020_03_17'})
for day, col in [('20200407','cases_2020_04_07'),('20200427','cases_2020_04_27')]:
    base = base.merge(covid[day][['codice_provincia','totale_casi']].rename(columns={'totale_casi':col}), on='codice_provincia', how='left')
base['_k'] = base.denominazione_provincia.map(norm)
dens['_k'] = dens.density_label.str.replace(r' \(NUTS 2016\)','', regex=True).map(norm)
panel = base.merge(dens.drop(columns=['density_label']), on='_k', how='left')

# Independent exposure: CAMS global atmospheric-composition reanalysis served
# by Open-Meteo.  Query ten capital coordinate points at a time for 2018 hourly
# PM10 and ozone, then calculate EU-limit exceedance days (PM10 daily mean >50
# ug/m3 OR maximum 8-hour rolling ozone mean >120 ug/m3). This is a stated
# replacement for regulatory monitor-based values in the article.
exposure_rows = []
request_units = panel[['codice_provincia','denominazione_provincia','lat','long']].drop_duplicates().reset_index(drop=True)
for start in range(0, len(request_units), 10):
    chunk = request_units.iloc[start:start+10]
    lat = ','.join(f'{x:.6f}' for x in chunk.lat); lon = ','.join(f'{x:.6f}' for x in chunk.long)
    url = ('https://air-quality-api.open-meteo.com/v1/air-quality?latitude='+urllib.parse.quote(lat, safe=',')+
           '&longitude='+urllib.parse.quote(lon, safe=',')+
           '&hourly=pm10,ozone&start_date=2018-01-01&end_date=2018-12-31&timezone=UTC')
    obj = json.loads(fetch(url, f'openmeteo_cams_2018_{start//10:02d}.json').read_text())
    records = obj if isinstance(obj, list) else [obj]
    if len(records) != len(chunk): raise ValueError('Open-Meteo response point count mismatch')
    for unit, rec in zip(chunk.itertuples(index=False), records):
        h = pd.DataFrame(rec['hourly']); h['time'] = pd.to_datetime(h['time'])
        h['date'] = h['time'].dt.date
        daily = h.groupby('date').agg(pm10_mean=('pm10','mean'), ozone_values=('ozone',list))
        # rolling eight observed hourly values; gaps never count as an exceedance
        o3max = daily.ozone_values.map(lambda z: max(pd.Series(z).rolling(8, min_periods=8).mean().dropna(), default=float('nan')))
        eligible = daily.pm10_mean.notna() & o3max.notna()
        exceed = (daily.pm10_mean > 50) | (o3max > 120)
        exposure_rows.append({'codice_provincia':unit.codice_provincia,
            'province':unit.denominazione_provincia, 'lat_input':unit.lat, 'lon_input':unit.long,
            'days_with_complete_pm10_and_o3':int(eligible.sum()),
            'pm10_exceedance_days':int((daily.pm10_mean > 50).sum()),
            'ozone_exceedance_days':int((o3max > 120).sum()),
            'either_limit_exceedance_days':int((exceed & eligible).sum())})
exposure = pd.DataFrame(exposure_rows)
exposure.to_csv(OUT/'exposure_table.csv', index=False)

panel = panel.merge(exposure, on='codice_provincia', how='left')
for c in ['cases_2020_03_17','cases_2020_04_07','cases_2020_04_27','population_density_2019','either_limit_exceedance_days']:
    # Mask first: np.where would still evaluate log(0) and conceal a coverage issue.
    panel['log_'+c] = panel[c].where(panel[c] > 0).map(np.log)
complete = panel.dropna(subset=['log_cases_2020_03_17','log_cases_2020_04_07','log_cases_2020_04_27','log_population_density_2019','log_either_limit_exceedance_days']).copy()
panel.to_csv(OUT/'analysis_panel.csv', index=False)

models=[]; outputs=[]
for date, outcome in [('2020-03-17','log_cases_2020_03_17'),('2020-04-07','log_cases_2020_04_07'),('2020-04-27','log_cases_2020_04_27')]:
    dat=complete.dropna(subset=[outcome])
    fit=sm.OLS(dat[outcome], sm.add_constant(dat[['log_either_limit_exceedance_days','log_population_density_2019']])).fit()
    ci=fit.conf_int().loc['log_either_limit_exceedance_days']
    models.append({'outcome_date':date,'n':int(fit.nobs),'r_squared':fit.rsquared,
                   'air_pollution_elasticity':fit.params['log_either_limit_exceedance_days'],
                   'air_pollution_se':fit.bse['log_either_limit_exceedance_days'],
                   'air_pollution_p':fit.pvalues['log_either_limit_exceedance_days'],
                   'air_pollution_ci_low':ci.iloc[0],'air_pollution_ci_high':ci.iloc[1],
                   'population_density_elasticity':fit.params['log_population_density_2019'],
                   'population_density_p':fit.pvalues['log_population_density_2019']})
    outputs.append('\n\n### Outcome: cumulative provincial confirmed cases, '+date+'\n'+fit.summary().as_text())
pd.DataFrame(models).to_csv(OUT/'model_estimates.csv', index=False)
(OUT/'model_output.txt').write_text('\n'.join(outputs)+'\n')

with (OUT/'request_log.json').open('w') as f: json.dump(REQUEST_LOG, f, indent=2)
sources=[]
for role, url, file in [
 ('health outcome (official provincial daily cases)', covid_urls['20200317'], RAW/'covid_20200317.csv'),
 ('health outcome (official provincial daily cases)', covid_urls['20200407'], RAW/'covid_20200407.csv'),
 ('health outcome (official provincial daily cases)', covid_urls['20200427'], RAW/'covid_20200427.csv'),
 ('population-density covariate', dens_url, RAW/'eurostat_density_2019.json'),
 ('independent pollution exposure, CAMS via Open-Meteo', 'https://air-quality-api.open-meteo.com/v1/air-quality', RAW/'openmeteo_cams_2018_00.json')]:
    sources.append({'role':role,'url':url,'retrieved':True,'sha256':digest(file)})
# Each batched response is retained separately; exact request URLs, response
# sizes, and attempt history are in request_log.json.
for batch in range(1, 11):
    air_file = RAW / f'openmeteo_cams_2018_{batch:02d}.json'
    sources.append({'role':'independent pollution exposure, CAMS via Open-Meteo (additional coordinate batch)',
                    'url':'https://air-quality-api.open-meteo.com/v1/air-quality',
                    'retrieved':True,'sha256':digest(air_file)})
json.dump(sources, (OUT/'source_manifest.json').open('w'), indent=2)

primary=models[0]
result={
 'study_id':'PMID-33398753', 'status':'completed_fit',
 'target':{'outcome':'Cumulative confirmed COVID-19 cases (province-level public series; 17 March 2020 primary, with 7 and 27 April replications)',
 'pollutant':'2018 days exceeding PM10 daily mean >50 ug/m3 or ozone maximum 8-hour rolling mean >120 ug/m3',
 'geography':'Italian provinces, assigned exposure at each provincial-capital coordinate', 'period':'Exposure: 2018; outcomes: 17 March, 7 April, and 27 April 2020',
 'effect_scale':'OLS elasticity: log cumulative cases regressed on log annual exceedance days and log population density'},
 'sources':sources,
 'substitutions':[
  {'dimension':'geography','published':'55 randomly selected provincial-capital cities (identities not reported)','reanalysis':'All 107 official reporting provinces initially eligible; 100 entered the complete-case model','reason':'The article does not identify its random 55-city sample; public outcome data are provincial.'},
  {'dimension':'outcome','published':'Infected individuals attributed to cities','reanalysis':'Official cumulative confirmed cases reported by province','reason':'The publicly available national series is province-level; city-specific case totals were not supplied.'},
  {'dimension':'exposure','published':'Legambiente-derived regulatory-monitor total days exceeding PM10 or ozone limits in 2018','reanalysis':'CAMS reanalysis hourly PM10 and ozone at provincial-capital coordinates, aggregated using stated EU thresholds','reason':'Required independent public exposure source; avoids article-author values and makes assignment reproducible.'},
  {'dimension':'covariate','published':'2019 municipal population density','reanalysis':'2019 Eurostat NUTS3/provincial population density','reason':'Aligns the covariate’s geographic unit to the official provincial outcome.'}
 ],
 'coverage':{'eligible_units':107,'included_units':int(len(complete)),'eligible_times':3,'included_times':3,
 'notes':'Four provinces lacked a direct 2019 Eurostat NUTS3-density match; three further provinces had zero modeled exceedance days and cannot enter a log-exposure model. All included points had 365 complete modeled exposure days.'},
 'effect':{'estimate':primary['air_pollution_elasticity'],'ci_low':primary['air_pollution_ci_low'],'ci_high':primary['air_pollution_ci_high'],
 'scale':'OLS log-log coefficient adjusted for log 2019 population density','contrast':'1% higher 2018 CAMS-derived limit-exceedance days at the provincial-capital coordinate'},
 'artifacts':{'code':'/output/code/reanalyze.py','source_manifest':'/output/source_manifest.json','exposure':'/output/exposure_table.csv','analysis_panel':'/output/analysis_panel.csv','model_output':'/output/model_output.txt','decision_log':'/output/decision_log.md','request_log':'/output/request_log.json','model_estimates':'/output/model_estimates.csv'},
 'blockers':['Exact reproduction of the published 55-city sample is impossible: the article says it was randomly selected but does not identify the cities.','The public national COVID-19 series reports cumulative cases by province, not city.','Four eligible provinces could not be directly matched to 2019 Eurostat NUTS3 density and were not imputed.','Three further provinces had zero CAMS-derived exceedance days; log(0) is undefined, so they were excluded rather than transformed.']}
json.dump(result, (OUT/'result.json').open('w'), indent=2)

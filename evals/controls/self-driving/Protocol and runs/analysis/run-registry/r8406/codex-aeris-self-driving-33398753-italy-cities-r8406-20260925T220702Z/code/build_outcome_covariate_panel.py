#!/usr/bin/env python3
"""Build the permitted city/province outcome-covariate table.

The article-linked workbook is used only for the 55-unit sampling frame and
2019 density. Its published pollution column and its infection columns are
intentionally not propagated. Outcomes are from DPC's public provincial daily
archive on the three dates described in the article.
"""
from pathlib import Path
import pandas as pd
import unicodedata

ROOT = Path('/output')
REC = ROOT / 'recovery'

def norm(x):
    x = unicodedata.normalize('NFKD', str(x)).encode('ascii', 'ignore').decode()
    return ''.join(c for c in x.lower() if c.isalnum())

source = pd.read_excel(REC / 'mendeley-source.xlsx', sheet_name='Data ')
frame = source[['City', 'Italian Province Capital', 'Density h/km2']].copy()
frame.columns = ['city_label', 'province', 'density_2019_per_km2']
frame['province_key'] = frame.province.map(norm)
# DPC's province labels include territorial qualifiers omitted by the article.
article_to_dpc = {
    'forli': 'forlicesena',
    'monza': 'monzaedellabrianza',
    'reggioemilia': 'reggionellemilia',
}
frame['province_key'] = frame.province_key.replace(article_to_dpc)
if frame.province_key.duplicated().any():
    raise ValueError('duplicate province in article sampling frame')

out = frame.copy()
for date in ('20200317', '20200407', '20200427'):
    d = pd.read_csv(REC / f'dpc-province-{date}.csv')
    # DPC uses codes 979--999 for regional "in definition" aggregates.
    # They are not provinces and must not be joined to provincial capitals.
    d = d.loc[d.codice_provincia.notna() & (d.codice_provincia.astype(int) < 900)].copy()
    d['province_key'] = d.denominazione_provincia.map(norm)
    if d.province_key.duplicated().any():
        raise ValueError(f'duplicate DPC province for {date}')
    d = d[['province_key','codice_provincia','denominazione_provincia','lat','long','totale_casi']]
    d.columns = ['province_key', 'province_code', 'dpc_province', 'latitude', 'longitude', f'infections_{date}']
    out = out.merge(d, on='province_key', how='left', validate='one_to_one', suffixes=('', '_dupe'))
    for c in ['province_code', 'dpc_province', 'latitude', 'longitude']:
        dupe = c + '_dupe'
        if dupe in out:
            out[c] = out[c].combine_first(out[dupe])
            out = out.drop(columns=dupe)

if out[['latitude','longitude','infections_20200317','infections_20200407','infections_20200427']].isna().any().any():
    print(out[out[['latitude','longitude','infections_20200317','infections_20200407','infections_20200427']].isna().any(axis=1)].to_string(index=False))
    raise ValueError('unmatched article provinces')
out = out.drop(columns='province_key').sort_values('province').reset_index(drop=True)
out.to_csv(ROOT / 'data' / 'outcome_covariate_panel.csv', index=False)
# AERIS-compatible static cohort; kept separate from analytic outcomes/covariates.
cohort = out[['province', 'latitude', 'longitude']].copy()
cohort.columns = ['subject_id', 'latitude', 'longitude']
cohort['start_date'] = '2018-01-01'
cohort['end_date'] = '2018-12-31'
cohort.to_csv(ROOT / 'data' / 'aeris_city_cohort.csv', index=False)
print(out.to_string(index=False))
print('rows=', len(out), 'density range=', (out.density_2019_per_km2.min(), out.density_2019_per_km2.max()))

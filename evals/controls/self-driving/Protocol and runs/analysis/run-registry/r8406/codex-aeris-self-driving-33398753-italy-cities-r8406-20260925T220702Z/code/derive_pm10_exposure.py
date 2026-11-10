#!/usr/bin/env python3
"""Derive locked annual PM10 exceedance count from AERIS exported daily records."""
from pathlib import Path
import pandas as pd

OUT = Path('/output')
files = sorted((OUT/'data').glob('aeris_exposure_chunk_*.csv'))
if not files:
    raise RuntimeError('no AERIS exports')
raw = pd.concat([pd.read_csv(p) for p in files], ignore_index=True)
raw['timestamp_utc'] = pd.to_datetime(raw.timestamp_utc, utc=True)
raw['date_utc'] = raw.timestamp_utc.dt.date.astype(str)
raw = raw.loc[raw.date_utc.between('2018-01-01','2018-12-31')].copy()
# Negative sentinel values are not physical PM10 concentrations.
raw = raw.loc[raw.value.ge(0)].copy()
raw.to_csv(OUT/'data'/'pm10_daily_observations_raw.csv', index=False)

# v3 and archive can overlap. Values are daily records; collapse duplicate
# subject-date readings by their median, retaining source count for diagnostics.
daily = (raw.groupby(['subject_id','date_utc'], as_index=False)
           .agg(pm10_daily_ug_m3=('value','median'), n_source_records=('value','size'),
                source_labels=('data_source', lambda x: '|'.join(sorted(set(x))))))
daily.to_csv(OUT/'data'/'pm10_daily_observations_deduplicated.csv', index=False)

exp = (daily.groupby('subject_id', as_index=False)
       .agg(observed_days=('date_utc','nunique'),
            pm10_exceedance_days_gt50=('pm10_daily_ug_m3', lambda x: int((x>50).sum())),
            pm10_daily_mean=('pm10_daily_ug_m3','mean'),
            pm10_daily_min=('pm10_daily_ug_m3','min'),
            pm10_daily_max=('pm10_daily_ug_m3','max'),
            duplicated_source_day_records=('n_source_records', lambda x: int((x>1).sum()))))
exp['coverage_fraction'] = exp.observed_days / 365
exp = exp.rename(columns={'subject_id':'province'})
all_units = pd.read_csv(OUT/'data'/'outcome_covariate_panel.csv')[['province']]
exp = all_units.merge(exp, on='province', how='left')
exp.to_csv(OUT/'data'/'pm10_exposure_2018.csv', index=False)
print(exp.to_string(index=False))
print('\ncoverage summary')
print(exp[['observed_days','coverage_fraction','pm10_exceedance_days_gt50']].describe().to_string())

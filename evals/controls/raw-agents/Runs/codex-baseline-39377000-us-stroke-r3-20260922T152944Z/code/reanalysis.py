#!/usr/bin/env python3
"""Reproducible, fail-closed independent reanalysis scaffold for PMID 39377000.

This script intentionally refuses to fit a substituted outcome.  It also
implements the required sanitization gate for any author-designated table:
pollution/exposure/fitted/derived columns are dropped before inspection.
"""
from pathlib import Path
import csv, json, re, zipfile

ROOT = Path('/output')
RAW = ROOT / 'raw'

def sanitize_author_table(src, dst, audit):
    """Drop forbidden author-supplied analytic fields before any inspection."""
    forbidden = re.compile(r'(pm\s*2?\.?5|pollut|expos|air.?quality|fit|predict|resid|model|attribut)', re.I)
    with open(src, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        kept = [x for x in reader.fieldnames if not forbidden.search(x)]
        dropped = [x for x in reader.fieldnames if forbidden.search(x)]
        with open(dst, 'w', newline='', encoding='utf-8') as o:
            writer = csv.DictWriter(o, fieldnames=kept); writer.writeheader()
            for row in reader: writer.writerow({k: row[k] for k in kept})
    Path(audit).write_text(json.dumps({'retained_columns': kept, 'dropped_columns': dropped}, indent=2)+'\n')

def make_monitor_exposure(zip_path, out_path):
    """Independent EPA AQS monitor daily PM2.5 -> county/year monitor mean.

    This is a monitor-based assignment (not the authors' exposure); it is
    deliberately not used for a model until compatible outcome/covariates exist.
    """
    cols = ['fips', 'year', 'pm25_ug_m3', 'n_daily_observations', 'assignment']
    with open(out_path, 'w', newline='') as out:
        w = csv.DictWriter(out, fieldnames=cols); w.writeheader()
        if not zipfile.is_zipfile(zip_path): return
        with zipfile.ZipFile(zip_path) as z:
            name = z.namelist()[0]
            sums, ns = {}, {}
            with z.open(name) as bf:
                for row in csv.DictReader((x.decode('latin1') for x in bf)):
                    # Prefer annual-average reporting convention but retain only
                    # 24-hour PM2.5 daily observations when available.
                    if row.get('Sample Duration') not in ('24 HOUR', '24-HR BLK AVG'): continue
                    try: value=float(row['Arithmetic Mean'])
                    except (KeyError, ValueError): continue
                    fips = row['State Code'].zfill(2)+row['County Code'].zfill(3)
                    sums[fips]=sums.get(fips,0)+value; ns[fips]=ns.get(fips,0)+1
            for fips in sorted(sums):
                w.writerow({'fips':fips,'year':2020,'pm25_ug_m3':sums[fips]/ns[fips],
                            'n_daily_observations':ns[fips],
                            'assignment':'mean of EPA AQS PM2.5 monitor daily arithmetic means; monitor counties only'})

if __name__ == '__main__':
    # No author table was supplied or used.  This creates the mandatory audit
    # record explicitly rather than pretending a sanitization occurred.
    (ROOT/'sanitization_audit.json').write_text(json.dumps({
      'author_designated_table_used': False, 'retained_columns': [], 'dropped_columns': [],
      'reason': 'No author table was used; public CDC Atlas proxy was independently downloaded.'}, indent=2)+'\n')
    make_monitor_exposure(RAW/'daily_88101_2020.zip', ROOT/'exposure_epa_aqs_2020.csv')

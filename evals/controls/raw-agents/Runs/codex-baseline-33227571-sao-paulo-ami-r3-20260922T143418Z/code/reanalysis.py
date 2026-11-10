#!/usr/bin/env python3
"""Independent public-data reanalysis attempt for PMID 33227571.

This script intentionally never consumes an author-supplied pollution field.
It retrieves independent, gridded historical pollution from Open-Meteo/CAMS.
The principal comparison is only fitted if a daily, record-level SIH outcome
file is present and passes the sanitizer and coverage checks.
"""
from __future__ import annotations
import csv, hashlib, json, pathlib, time, urllib.error, urllib.parse, urllib.request
from datetime import date, timedelta

OUT = pathlib.Path('/output')
RAW = OUT / 'raw'
RAW.mkdir(parents=True, exist_ok=True)
URL_TEMPLATE = ('https://air-quality-api.open-meteo.com/v1/air-quality?latitude=-23.5505&longitude=-46.6333'
       '&hourly=pm2_5,pm10,nitrogen_dioxide,temperature_2m,relative_humidity_2m,precipitation'
       '&start_date={year}-01-01&end_date={year}-12-31&timezone=America%2FSao_Paulo')

def request(url: str, destination: pathlib.Path):
    """Transport-only retry policy: 5 attempts for transient errors, logged."""
    log = []
    for attempt, delay in enumerate((0, 5, 15, 45, 120), 1):
        if delay: time.sleep(delay)
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'independent-reanalysis/1.0'})
            with urllib.request.urlopen(req, timeout=60) as response:
                body = response.read()
                code = response.status
            log.append({'attempt': attempt, 'url': url, 'http_status': code, 'bytes': len(body), 'delay_before_s': delay})
            if code == 200 and body:
                tmp = destination.with_suffix(destination.suffix + '.tmp')
                tmp.write_bytes(body); tmp.replace(destination)
                return log
            if 400 <= code < 500:
                break
        except urllib.error.HTTPError as e:
            log.append({'attempt': attempt, 'url': url, 'http_status': e.code, 'error': str(e), 'bytes': 0, 'delay_before_s': delay})
            if 400 <= e.code < 500:
                break
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            log.append({'attempt': attempt, 'url': url, 'error': str(e), 'bytes': 0, 'delay_before_s': delay})
    raise RuntimeError(json.dumps(log))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    log, raw_files = [], []
    # Archive support begins in 2013. Retain the rejected 2012 request as
    # coverage evidence, rather than silently shortening the published period.
    try:
        log += request(URL_TEMPLATE.format(year=2012), RAW / 'openmeteo_2012.json')
    except RuntimeError as e:
        log += json.loads(str(e))
    for year in (2013, 2014, 2015):
        raw = RAW / f'openmeteo_{year}.json'
        log += request(URL_TEMPLATE.format(year=year), raw)
        raw_files.append(raw)
    (OUT / 'request_log.json').write_text(json.dumps(log, indent=2) + '\n')
    fields = ['pm2_5', 'pm10', 'nitrogen_dioxide', 'temperature_2m', 'relative_humidity_2m', 'precipitation']
    daily = {}
    for raw in raw_files:
        h = json.loads(raw.read_text())['hourly']
        for i, stamp in enumerate(h['time']):
            d = stamp[:10]
            daily.setdefault(d, {f: [] for f in fields})
            for f in fields:
                v = h.get(f, [None] * len(h['time']))[i]
                if v is not None: daily[d][f].append(v)
    with (OUT / 'exposure_daily.csv').open('w', newline='') as fp:
        w = csv.DictWriter(fp, fieldnames=['date'] + fields)
        w.writeheader()
        for d in sorted(daily):
            row = {'date': d}
            for f in fields:
                vals = daily[d][f]
                row[f] = sum(vals) / len(vals) if vals else ''
            # A timestamp-only response is not an exposure measurement.
            if all(row[f] != '' for f in fields):
                w.writerow(row)
    exp_rows = sum(1 for _ in (OUT / 'exposure_daily.csv').open()) - 1
    # No SIH microdata were retrieved.  This preserves a deliberately empty panel;
    # a fitted comparison is prohibited rather than inferred from exposure alone.
    with (OUT / 'analysis_panel.csv').open('w', newline='') as fp:
        csv.DictWriter(fp, fieldnames=['date','ami_admissions','cluster']).writeheader()
    (OUT / 'health_column_sanitization.json').write_text(json.dumps({
        'source_table': None, 'inspection_performed': False,
        'retained_columns': [], 'dropped_columns': [],
        'reason': 'No daily SIH outcome file was retrievable; no author-designated table was used.'
    }, indent=2) + '\n')
    (OUT / 'model_output.txt').write_text(
        'NO MODEL FIT\nDaily AMI admissions were unavailable, so the locked cluster comparison was not estimable.\n'
        f'Independent exposure rows constructed: {exp_rows} (2013--2015 only).\n'
        + '\n'.join(f'{p.name} SHA-256: {sha(p)}' for p in raw_files) + '\n')

if __name__ == '__main__': main()

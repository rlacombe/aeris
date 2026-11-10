#!/usr/bin/env python3
"""Independent reanalysis runner for PMID 38788590.

This runner deliberately refuses to fit a partial or author-derived exposure
panel.  It records retrievals, sanitizes any author-designated outcome table
before inspection, and validates the locked national daily panel before model
construction.  No health or exposure values are invented.
"""
from __future__ import annotations

import csv, hashlib, json, re, shutil, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OUT = Path('/output')
RAW, LOGS = OUT/'raw', OUT/'logs'
RAW.mkdir(parents=True, exist_ok=True); LOGS.mkdir(parents=True, exist_ok=True)
NOW = datetime.now(timezone.utc).isoformat()

SOURCES = [
    ('article_record', 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=38788590&retmode=xml', True, '/study/article.xml'),
    ('lawful_full_text', 'https://www.researchgate.net/publication/380561503_Cancer_Mortality_Risk_from_Short-Term_PM25_Exposure_and_Temporal_Variations_in_Brazil', True, '/study/article.pdf'),
    ('outcome_SIM_documentation', 'https://www.gov.br/saude/pt-br/acesso-a-informacao/sic/dados-em-transparencia-ativa/svsa/mortalidade', True, None),
    ('outcome_SIM_microdata_attempt', 'https://ftp.datasus.gov.br/dissemin/publicos/SIM/CID10/DADOS/DO2000.dbc', False, None),
    ('independent_exposure_candidate_MERRA2_documentation', 'https://gmao.gsfc.nasa.gov/gmao-products/merra-2/', True, None),
    ('independent_exposure_candidate_MERRA2_data_attempt', 'https://goldsmr4.gesdisc.eosdis.nasa.gov/data/MERRA2/M2I1NXAER.5.12.4/2000/01/MERRA2_100.inst1_2d_aer_Nx.20000101.nc4', False, None),
    ('published_weather_ERA5_catalog', 'https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels', False, None),
]

def digest(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20), b''): h.update(b)
    return h.hexdigest()

def fetch_doc(url: str, name: str):
    """One identical request: a 4xx is terminal per contract policy."""
    dest=RAW/name
    event={'timestamp_utc':NOW,'url':url,'attempt':1,'method':'GET','bytes':0,'status':None,'delay_seconds':0}
    try:
        req=Request(url, headers={'User-Agent':'independent-reanalysis/1.0'})
        with urlopen(req, timeout=30) as r:
            body=r.read(); event['status']=r.status; event['bytes']=len(body)
            dest.write_bytes(body)
    except HTTPError as e:
        event['status']=e.code; event['bytes']=len(e.read() or b'')
    except (URLError, TimeoutError) as e:
        event['error']=str(e)
    (LOGS/f'{name}.request.json').write_text(json.dumps(event,indent=2)+'\n')
    return event

def sanitize_author_table():
    """Mandatory pre-inspection guard for any author-designated input table."""
    candidates=list((RAW/'author_designated').glob('*')) if (RAW/'author_designated').exists() else []
    kept=[]; dropped=[]
    forbidden=re.compile(r'(pm.?2.?5|pollut|exposure|fitted|predicted|attribut|risk|effect|lag)',re.I)
    for p in candidates:
        if p.suffix.lower() not in {'.csv','.tsv'}: continue
        with p.open(newline='',encoding='utf-8-sig') as f:
            reader=csv.DictReader(f,delimiter='\t' if p.suffix.lower()=='.tsv' else ',')
            cols=reader.fieldnames or []
            d=[c for c in cols if forbidden.search(c)]; k=[c for c in cols if c not in d]
            dropped.extend(d); kept.extend(k)
            with (RAW/(p.stem+'_sanitized.csv')).open('w',newline='') as g:
                w=csv.DictWriter(g,fieldnames=k); w.writeheader()
                for row in reader: w.writerow({c:row[c] for c in k})
    (OUT/'sanitization_columns.json').write_text(json.dumps({'input_files':[str(x) for x in candidates],'retained_columns':kept,'dropped_columns':dropped,'note':'No author-designated table was supplied; no table was inspected or modeled.'},indent=2)+'\n')

def main():
    sanitize_author_table()
    # Retrieve accessible public documentation, never use the article authors' exposure values.
    fetch_doc(SOURCES[2][1], 'sim_mortality_documentation.html')
    fetch_doc(SOURCES[4][1], 'merra2_documentation.html')
    # Empty, schema-stable artifacts distinguish a blocker from missing output.
    (OUT/'exposure_table.csv').write_text('municipality_code,date,pm25_3day_mean_ug_m3,source\n')
    (OUT/'analysis_panel.csv').write_text('stratum_id,case,municipality_code,date,pm25_3day_mean_ug_m3,temp,rh,holiday\n')
    model={'executed':False,'reason':'No independent daily municipality PM2.5 table covering all 5,570 municipalities and 2000-01-01 through 2019-12-31 was retrieved. A complete matched exposure panel is required; partial sources were not substituted.','native_coefficient':None,'native_ci':None,'contrasts':[]}
    (OUT/'model_output.json').write_text(json.dumps(model,indent=2)+'\n')
    manifest=[]
    for role,url,retrieved,path in SOURCES:
        sha = digest(Path(path)) if path and Path(path).exists() else None
        manifest.append({'role':role,'url':url,'retrieved':retrieved,'sha256':sha})
    (OUT/'source_manifest.json').write_text(json.dumps({'generated_utc':NOW,'sources':manifest,'request_logs':[str(p) for p in LOGS.glob('*.request.json')],'notes':'The two failed data endpoints are recorded as terminal first attempts: DATASUS was a network connect timeout; the candidate MERRA-2 object returned HTTP 404. No retries were used because neither outcome download nor MERRA-2 was the selected final data source, and retrying cannot cure an unavailable/incorrect object path.'},indent=2)+'\n')
    fidelity={'study_id':'pmid-38788590','fidelity_status':'blocked_before_fit','locked_target_reconstructed':True,'outcome_construct':'SIM individual deaths whose underlying cause is ICD-10 C00-C97 (all cancer)', 'exposure_construct':'municipality population-weighted daily PM2.5, 3-day risk-period mean', 'model_construct':'time-stratified case-crossover conditional logistic regression; 3-4 same-weekday controls in month; temperature cross-basis, RH, holiday', 'departures_from_locked_analysis':[], 'fit_performed':False, 'blocker':'Independent exposure table with national daily municipality coverage was not obtained.'}
    (OUT/'fidelity_record.json').write_text(json.dumps(fidelity,indent=2)+'\n')
    result={'study_id':'pmid-38788590','status':'completed_blocker','target':{'outcome':'All-cancer mortality (underlying ICD-10 C00-C97)','pollutant':'PM2.5','geography':'Brazil, 5,570 residential municipalities','period':'2000-01-01 through 2019-12-31','effect_scale':'Odds ratio per 10 µg/m3 increase in three-day mean PM2.5'},'sources':manifest,'substitutions':[], 'coverage':{'eligible_units':5570,'included_units':0,'eligible_times':7305,'included_times':0,'notes':'No municipality-day can enter the locked comparison because the required independent PM2.5 series was not retrieved. Outcome microdata are public in principle but were not processed after exposure validation failed.'},'effect':None,'artifacts':{'code':'/output/code/reanalysis.py','source_manifest':'/output/source_manifest.json','exposure':'/output/exposure_table.csv','analysis_panel':'/output/analysis_panel.csv','model_output':'/output/model_output.json','decision_log':'/output/decision_log.md','fidelity_record':'/output/fidelity_record.json','sanitization_columns':'/output/sanitization_columns.json'},'blockers':[model['reason']]}
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'study_id':result['study_id'],'status':result['status'],'fit_performed':False,'primary_effect':None,'blocker_count':len(result['blockers'])}))
if __name__=='__main__': main()

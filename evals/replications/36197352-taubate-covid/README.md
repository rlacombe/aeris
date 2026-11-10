# Taubate COVID-19 admissions

This directory contains the canonical reconstruction of PMID 36197352.
It keeps the paper's three-municipality outcome, study dates, pollutants,
lag scan, and negative-binomial model. AERIS identifies the local monitor;
the public CETESB historical form supplies the complete daily record after
the OpenAQ archive ends during the study window.

Run in order:

```bash
python scripts/run_aeris_discovery.py
python scripts/fetch_cetesb_daily.py
python scripts/fetch_sih_sus.py
python scripts/ingest_sih_sus.py
python scripts/fetch_weather.py
python scripts/build_panel.py
python scripts/fit_negative_binomial.py
```

The run writes only under this directory. `source_manifest.json` records the
public source routes and every derived file is accompanied by a summary or
manifest.

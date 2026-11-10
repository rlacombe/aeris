# Northern Italy COVID-19

This directory reconstructs PMID 34004167 with public Italian Civil Protection
outcomes and AERIS boundary aggregation. The study covers Lombardia and Veneto.
The AERIS estimand is the unweighted mean of daily monitor means inside each
named regional boundary.

## Completed run

The study's PM2.5 field could not be reconstructed from OpenAQ. The archive
objects for 28 Lombardia locations contained no PM2.5 rows, and Veneto had no
PM2.5 location that overlapped the epidemic window.

OpenAQ did provide daily NO2 for both regions from 6 to 19 May 2020. NO2 is a
published short-term pollutant term, so the directory includes a 28 region-day
NO2 reconstruction and the closest supported GEE.

## Reproduce

```bash
export PYTHONPATH=.
export MPLCONFIGDIR=/tmp/aeris-matplotlib
PYTHON=python

$PYTHON aeris-openaq-s3/run_aeris_no2_overlap.py
$PYTHON aeris-openaq-s3/build_no2_overlap_panel.py
$PYTHON aeris-openaq-s3/fit_no2_overlap_gee.py
$PYTHON aeris-openaq-s3/write_run_manifest.py
```

`RESULT.md` records the model, scope, and eligibility decision. The raw source
files, tool trace, exposure panel, station table, output manifest, and model
result remain under `aeris-openaq-s3/`.

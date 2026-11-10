# PMID 33398753: Italian Provincial Capitals COVID-19

This directory contains the AERIS source-substitution reanalysis of the
Italian provincial-capitals COVID-19 study. It uses public city-level outcomes
and independently reconstructed AERIS/OpenAQ PM10 records for 2018. It does
not read the article's exposure values.

## Run order

```bash
python run_aeris_tools.py
python fit_effect.py
```

For the expanded city-coverage run:

```bash
python run_aeris_full_coverage.py
python fit_full_coverage_effect.py
```

`RESULT.md` records the published contrast, reconstructed effect, city count,
and time coverage. The shared reanalysis instruction is summarized in
[`../../docs/REPLICATION_PROMPT_SUMMARIES.md`](../../docs/REPLICATION_PROMPT_SUMMARIES.md).

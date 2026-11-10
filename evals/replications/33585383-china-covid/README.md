# PMID 33585383: China COVID-19 and PM2.5

Independent AERIS reproduction of Pansini and Fornacca, *COVID-19 Higher
Mortality in Chinese Regions With Chronic Exposure to Lower Air Quality*
(2021), DOI `10.3389/fpubh.2020.597753`.

## Target analysis

The paper's PM2.5 result is a prefecture-level Kendall rank correlation between
2014-2016 ground-station PM2.5 and COVID-19 mortality (deaths / cases * 100),
reported as `tau = 0.18`, `p < 0.001`, `n = 287`. It is not a
covariate-adjusted regression. This reproduction fits that same unadjusted
Kendall tau-b analysis after replacing the paper's PM2.5 field with
AERIS/OpenAQ exposure records.

## Public inputs

`acquire_public_inputs.py` downloads the authors' public prefecture-level table
from their GitHub repository. It verifies the expected SHA-256 checksum, then
writes `public_inputs/outcomes_without_author_exposure.csv`. That model input
contains only public outcomes, population, population density, and location
labels. Every author-provided satellite and ground-pollution column is excluded.

The raw source table remains in `public_inputs/` for provenance only and is not
read by `run_aeris_tools.py` or `fit_model.py`.

## AERIS reconstruction

The AERIS static tool is called with daily PM2.5, China country-catalog station
discovery, a 100 km nearest-monitor assignment for prefecture-level locations,
and its study-local OpenAQ cache.
The requested 2014-2016 interval exceeds AERIS's 400-day automatic public-S3
archive window. `run_aeris_tools.py` submits each calendar year in 25-prefecture
cohorts. Each successful cohort is exported immediately, so an upstream archive
timeout cannot discard a completed annual panel. `fit_model.py` combines annual
means using their AERIS observed-day counts.

The prior full-window attempt is retained in `aeris_tool_trace.json`; it
returned zero usable records because the three-year archive interval was not
fetched. The resumable annual-run trace is written to
`aeris_annual_tool_trace.json`; `aeris_reconstruction.log` records the exact
tool execution.

## Run

```bash
export MPLCONFIGDIR=/tmp/aeris-mpl
export PYTHONPATH=.
PY=python

$PY acquire_public_inputs.py
$PY run_aeris_tools.py
$PY fit_model.py
```

`model_result.json` and `analysis_panel.csv` are the final fitted result and
the exact public outcome plus reconstructed-exposure analysis panel.

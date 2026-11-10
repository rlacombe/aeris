# France COVID-19 Mortality Reproduction

This directory contains an independent AERIS reproduction attempt for Tchicaya
et al. (2021), PMID 34488764. The original study analysed cumulative hospital
COVID-19 deaths across 96 mainland French departments with a negative-binomial
model and long-term PM2.5 exposure.

The reproduction keeps the published geography, outcome definition, modelling
family, and May 1, 2020 target date. It replaces the paper's 1999-2016
satellite-derived PM2.5 exposure with an AERIS/OpenAQ monitor-network annual
record for 2019, reconstructed independently for each department. The exposure
replacement is intentional and is recorded in the run manifest.

Install `requirements.txt`, then run `download_inputs.py`,
`build_analysis_panel.py`, `run_aeris_exposure.py`, and `fit_model.py` in that
order from this directory. Downloaded and derived artifacts are ignored until
the run is complete and reviewed.

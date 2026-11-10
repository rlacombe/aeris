# Code Inventory

Each study directory below contains the code used for its AERIS
source-substitution reanalysis, including attempts that ended in a documented
coverage or input failure. `README.md`, `REPLICATION.md`, and `RESULT.md`
describe the target, execution status, and outputs.

| PMID | Study directory | Primary executable code |
| --- | --- | --- |
| 33227571 | `replications/33227571-sao-paulo-ami/` | `scripts/fetch_*.py`, `scripts/ingest_sih.py`, `scripts/run_aeris_exposure.py`, `scripts/build_panel.py`, `scripts/fit_clusters.py` |
| 33398753 | `replications/33398753-italy-cities/` | `run_aeris_tools.py`, `run_aeris_full_coverage.py`, `fit_effect.py`, `fit_full_coverage_effect.py` |
| 33484722 | `replications/33484722-oecd-covid/` | `acquire_public_inputs.py`, `prepare_inputs.py`, `run_aeris_tools.py`, `fit_reproduction.py` |
| 33585383 | `replications/33585383-china-covid/` | `acquire_public_inputs.py`, `run_aeris_tools.py`, `fit_model.py` |
| 34004167 | `replications/34004167-northern-italy-covid/` | `run_aeris_tools.py`, `run_pm10_aeris_tools.py`, `aeris-openaq-s3/` execution scripts |
| 34260961 | `replications/34260961-israel-covid/` | `build_public_inputs.py`, `run_aeris_tools.py`, `audit_historical_pm25_catalog.py`, `fit_public_model.py` |
| 34389545 | `replications/34389545-wildfire-covid/` | `run.sh`, `run_reconstruction.py` |
| 34488764 | `replications/34488764-france-covid/` | `download_inputs.py`, `build_analysis_panel.py`, `run_aeris_exposure.py`, `fit_model.py` |
| 36197352 | `replications/36197352-taubate-covid/` | `scripts/run_aeris_discovery.py`, `scripts/fetch_*.py`, `scripts/build_panel.py`, `scripts/fit_negative_binomial.py` |
| 36383802 | `replications/36383802-sao-jose-covid/` | `scripts/fetch_*.py`, `scripts/ingest_*.py`, `scripts/run_aeris_tools.py`, `scripts/build_panel.py`, `scripts/fit_reproduction.py` |
| 38182658 | `replications/38182658-uk-covid/` | `run_aeris_tools.py`, `build_ecad_weather.py`, `fit_exploratory_model.py` |
| 38249516 | `replications/38249516-alaska-wildfire-asthma/` | `scripts/acquire_geography.py`, `scripts/reconstruct_pm25.py`, `scripts/fit_analysis.py` |
| 38788590 | `replications/38788590-brazil-cancer/` | `scripts/fetch_*.py`, `scripts/ingest_sim.py`, `scripts/run_aeris_exposure.py`, `scripts/build_panel.py`, `scripts/fit_case_crossover.py` |
| 39377000 | `replications/39377000-us-stroke/` | `build_atlas_proxy_panel.py`, `run_aeris_tools.py`, `build_adjusted_public_panel.py`, `fit_adjusted_public_model.py` |
| 39689648 | `replications/39689648-argentina-covid/` | `scripts/acquire_public_inputs.py`, `scripts/build_outcomes.py`, `scripts/prepare_boundaries.py`, `scripts/run_aeris_exposure.py` |

## Shared benchmark code

`scripts/build_final_manifest.py` rebuilds the candidate manifest.
`scripts/summarize_*.py` creates the direction and calibration summaries.
`scripts/plot_effect_*.py` creates the comparison figures. The literature
search scripts and review prompt are under `literature-search/`.

## Required study outputs

Every study directory must retain its source manifest, AERIS trace, exposure
record or coverage diagnostic, executable model code, and result record. Raw
downloads may be stored once under `data-acquisition/` when they are too large
to duplicate; the study manifest must point to the exact source and file.

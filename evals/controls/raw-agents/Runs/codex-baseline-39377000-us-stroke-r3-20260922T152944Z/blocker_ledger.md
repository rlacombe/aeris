# Blocker ledger

## B1 — exact outcome unavailable in retrieved public release

**Status:** terminal for this run; `completed_blocker`.

The required outcome is county-level ischemic and hemorrhagic stroke mortality for adults aged 65+ over 2016–2020. The accessible CDC Atlas CSV is county/state all-stroke mortality for adults 35+, 2018–2020 (three-year average; age-adjusted and spatially smoothed). This is a different disease grouping, age universe, and time construction. It was retained only as verification evidence at `raw/cdc_atlas_all_stroke_2018_2020.csv` and not used in `analysis_panel.csv`.

CDC WONDER D176 returned HTTP 500; header/body evidence was captured during the request. An alternative public CDC outcome release was assessed rather than treating a new query or substitution as a transport retry.

## B2 — principal adjusted panel cannot be constructed

Because B1 prevents target mortality fields, no panel can combine those fields with PM2.5 and the 11 listed non-exposure covariates. The EPA file alone covers only monitor counties and only 2020, so it does not repair B1 or support the manuscript's national 2016–2020 analysis. The empty, schema-preserving analysis panel and unexecuted model record make this refusal auditable.

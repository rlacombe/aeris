# Decision log — independent reanalysis of PMID 34004167

## Locked reconstruction target

- Outcome: daily accumulated confirmed COVID-19 cases and accumulated deaths (the paper's incidence and mortality count outcomes).
- Geography/unit: Lombardy and Veneto; one region-day per outcome.
- Published period: 21 February through 19 May 2020.  The independent Civil Protection regional release begins on 24 February 2020, so the reconstructed period is 24 February through 19 May (86 dates × 2 regions).
- Pollutants: SO2 (principal pollutant highlighted by the paper), NO2, O3, PM2.5, and PM10.
- Exposure: same-day regional mean (STAP) and observed-day mean from 2013-01-01 through 2020-05-19 (LTAP), independently rebuilt from EEA E1a station measurements.  Station coordinates were assigned to Lombardy/Veneto using GADM ADM1 polygons; observations were averaged instrument-day, then station-day, then region-day. Negative EEA sentinel values (for example -9999) were removed, not treated as concentrations.
- Intended model: Poisson log-link GEE with AR(1) working correlation, region as GEE group, STAP + LTAP + a post-2020-02-21 lockdown indicator. Native contrast is beta (log rate ratio) per 1 ug/m3; transformed contrast is exp(beta), the RR per 1 ug/m3.

## Coverage and substitutions

- The outcome source has no rows for 21--23 February. This is a disclosed temporal substitution, not an imputation.
- EEA station coverage produced 2,331 distinct observed days per pollutant-region in the LTAP window, rather than all 2,696 calendar days. LTAP is therefore the mean of observed region-days, with no gap filling.
- All 172 reconstructed region-days have values for every short-term pollutant. The outcome dates have complete values in both regions.
- The study's reported population/density and meteorology covariates were not in its primary formula. Meteorology was a supplementary sensitivity analysis and was not added here.

## Modeling decision

The exact principal model is not identifiable from the reconstructed public panel. Every retained date is after the paper's declared lockdown date (2020-02-22), so `lockdown=1` on all 172 observations and is perfectly collinear with the intercept. Moreover, GEE inference is based on only two groups (Lombardy and Veneto); the robust covariance warnings and implausibly precise intervals in `model_output.csv` demonstrate that these are not valid confidence intervals.

For transparency, `reanalysis.py` executed the specified-form models using a pseudoinverse-capable implementation and saved all 20 diagnostic STAP/LTAP coefficients in `model_output.csv`. They are labeled `diagnostic_fit`, are not a principal estimate, and must not be interpreted as inferential results. The run is consequently `completed_blocker` and `result.json` intentionally has `effect: null`.

## Author-table sanitization

No author-designated analysis table, author pollution values, derived exposure field, fitted value, or author code was used. The independent outcome source was read as raw Civil Protection columns only. `sanitization.json` records this non-use and the retained outcome columns.

## Fidelity record

No executable `record_reanalysis_fidelity` utility was present in the supplied contract environment. The equivalent structured fidelity artifact was created as `fidelity_record.json`; its path is referenced from `result.json` under `artifacts.fidelity_record`.

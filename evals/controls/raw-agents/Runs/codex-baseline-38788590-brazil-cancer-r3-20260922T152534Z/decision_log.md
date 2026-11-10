# Decision log — PMID 38788590

## Locked reconstruction

- Outcome: individual Brazilian SIM deaths, all cancers (ICD-10 C00–C97), 1 January 2000–31 December 2019.
- Geography/unit: residential municipality; 5,570 municipalities; one case stratum per death.
- Exposure: daily municipality PM2.5, population-weighted across 0.25° grids; primary risk-period exposure is the three-day mean.
- Controls: three or four dates on the same day of week in the same calendar month and municipality.
- Model: conditional logistic regression, with a distributed-lag temperature cross-basis, relative humidity, and public-holiday indicator. The case-crossover matching controls age, sex, socioeconomic status, long-term trend, seasonality, and weekday by design.
- Primary contrast: 10 µg/m3 increase in three-day mean PM2.5. The model-native coefficient is beta per 1 µg/m3; the reported OR would be `exp(10 * beta)`, and the interval would be `exp(10 * CI_beta)`.

## Evidence and decisions

1. The supplied citation record gave the outcome, period, national scope, three-day PM2.5 contrast, and reported published result, but that result was not reused.
2. The lawful full-text copy established that the paper used a global daily 0.25° random-forest PM2.5 product, ERA5 temperature/dew point (converted to RH), WorldPop grid populations, and the model above. Its PM values and derived exposures are prohibited for this reanalysis and were not acquired.
3. Brazil's Ministry of Health documents public anonymized SIM microdata and municipality-level availability. A direct legacy FTP test from this run timed out. Because no independent national daily PM2.5 panel was retrieved, the 34.5-million-record outcome extraction was not started: it could not produce a valid fitted panel.
4. NASA MERRA-2 was assessed as an independent long-term aerosol-reanalysis candidate. Its documentation confirms coverage beginning in 1980 and aerosol assimilation, but the tested object URL returned 404; it also is an aerosol-component product rather than a ready daily PM2.5 field. It was not substituted for the locked exposure.
5. No partial period, subset of municipalities, non-daily exposure, author release, unadjusted model, or fabricated value was used. The run therefore ends as `completed_blocker`, not a failed model.

## Author-table sanitization

`/output/code/reanalysis.py` runs the mandatory pre-inspection sanitizer for any table placed in `/output/raw/author_designated/`. It removes columns whose names indicate pollution/exposure, fitted or predicted values, or derived effects/risks/attribution and records retained/dropped names. No author-designated table was supplied in this run; see `sanitization_columns.json`.

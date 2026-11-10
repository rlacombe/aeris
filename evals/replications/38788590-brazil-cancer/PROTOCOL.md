# Protocol

## Question

Can a researcher use public SIM mortality records and AERIS's monitor-based municipal PM2.5 reconstruction to execute a transparent approximation of the short-term PM2.5-cancer mortality analysis in Yu et al. (2024)?

## Paper-aligned elements

- Outcome records: Brazilian SIM deaths, identified by residential municipality, date of death, age, sex, and underlying ICD-10 cause.
- Study window: one calendar year, 2019, within the paper's 2000-2019 period.
- Geography: Sao Paulo municipality, selected before seeing the reconstructed association because it is the largest municipality in the state file and a plausible high-monitor-density test case.
- Cancer selection: the exact site definitions stated in Methods 2.1 of the paper: oral (`C00-C10`, `C12-C14`), nasopharynx (`C11`), oesophagus (`C15`), stomach (`C16`), colon/rectum (`C18-C21`), liver (`C22`), gallbladder (`C23-C24`), pancreas (`C25`), larynx (`C32`), lung (`C33-C34`), bone (`C40-C41`), skin (`C43`), breast (`C50`), cervix (`C53`), uterus (`C54-C55`), ovary (`C56`), prostate (`C61`), testis (`C62`), kidney (`C64-C66`), bladder (`C67`), brain (`C70-C72`), lymphoma (`C81-C85`), and leukemia (`C91-C95`).
- Referent construction: dates on the same weekday and in the same calendar month as each death date.
- Main exposure: 3-day moving average PM2.5, lag 0-2.
- Effect scale: odds ratio per 10 ug/m3.

## Deliberate substitutions and limits

1. Published PM2.5 was a population-weighted, 0.25-degree, all-source machine-learning surface. The recorded AERIS/OpenAQ boundary request found 12 eligible São Paulo PM2.5 locations but returned no 2019 observations. The completed run uses CETESB's public historical daily record for AERIS-selected station 31, Cid.Universitária-USP-Ipen, inside the IBGE polygon.
2. The paper used population-weighted ERA5 temperature and relative humidity, with a distributed-lag temperature cross-basis. This run uses daily centroid weather from Open-Meteo and a linear 3-day mean temperature adjustment. It is a covariate substitute, not an ERA5 reconstruction.
3. The paper's conditional logistic model operates at the death-record level. The implementation uses a mathematically equivalent weighted conditional likelihood over death dates: each day contributes its cancer death count times the case-crossover stratum likelihood. It does not expand identical day-level covariate rows once per death.
4. Scope: São Paulo municipality, calendar year 2019, all selected cancer deaths. National results, site-specific models, temporal meta-analysis, attributable deaths, and the original sensitivity analyses remain future work.

## Fit eligibility

The fitter requires at least 180 calendar days with complete outcome, AERIS PM2.5, and weather values, and at least 20 cancer deaths. It records the actual coverage before attempting an effect estimate. A failure to meet this threshold is a result about the current public monitoring reconstruction, not evidence about the original paper's exposure surface.

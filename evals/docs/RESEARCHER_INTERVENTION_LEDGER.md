# Researcher-intervention ledger

## Scope

This ledger describes researcher guidance during the nine-study AERIS
reanalysis campaign. It was reconstructed from the project conversation,
per-study code and result notes, prompt summaries, and the later supervision
audit. The campaign did not retain one canonical turn-by-turn transcript, so
exact intervention counts cannot be recovered. We report documented
intervention classes instead of estimating a false count.

The agent independently found papers and public data, wrote retrieval and
analysis code, reconstructed exposure, built analysis panels, and fitted the
models. Researcher input concentrated at scientific branch points: continuing
after a failed route, broadening coverage, preserving the intended estimand,
matching the article's effect scale, or approving a labeled fallback.

## Evidence labels

- **Direct:** the project conversation records the intervention.
- **Reconstructed:** study artifacts and prompt summaries establish the
  guidance, but its exact wording is unavailable.
- **Interpretive:** the intervention concerned classification or reporting
  after fitting rather than execution.

## Study-level ledger

| Study | Evidence | Researcher intervention | Category | Resulting agent action | Scientific effect |
| --- | --- | --- | --- | --- | --- |
| France COVID-19 | Direct + reconstructed | Continue the department-level run, broaden completed geographic coverage, and disclose the mismatch between the article's 1999--2016 exposure surface and the available 2019 monitor record. | Continue; broaden coverage; label substitution | Resumed department batches and fitted the covered public panel. | Increased coverage and made the exposure-period substitution explicit; it did not select an estimate by agreement. |
| Italian cities COVID-19 | Direct | Do not stop with eight cities; recover the largest defensible city sample. Report the article's positive PM10 result on its stated doubling scale and keep it separate from the article's null result. | Broaden coverage; preserve estimand; match scale | Expanded city retrieval and converted the fitted log-log coefficient to the reported doubling contrast. | Changed sample coverage and presentation scale while preserving the target estimand. |
| Sao Jose COVID-19 admissions | Direct + reconstructed | Continue after the SIH/SUS route failed and permit a clearly labeled public outcome fallback while retaining the article's lag structure. | Continue; approve bounded fallback | Used public SIVEP-Gripe admissions and fitted the available pollutant-day panel. | Changed the outcome definition and coverage period; the result was labeled bounded and excluded from strict calibration where required. |
| Sao Paulo acute myocardial-infarction admissions | Direct + reconstructed | Continue when the complete pollutant-cluster specification could not be recovered; permit a reduced-input sensitivity using public admissions, weather, and available pollution data. | Continue; approve reduced model | Built and fitted a reduced-input cluster analysis. | Reduced model fidelity while retaining an interpretable pollutant-health analysis. |
| United Kingdom COVID-19 | Reconstructed | Recover the four national outcome series, construct nation-day exposure, fit the viable core model, and add public weather covariates when available. | Continue; modular recovery; approve core model | Built outcome, exposure, and weather components separately before fitting the available panel. | Preserved the target geography and pollutant while using the strongest executable public-data model. |
| United States stroke mortality | Direct + reconstructed | Continue the county analysis, use a deterministic bounded sample and public outcome proxy when necessary, and express the result on the article's per-10-ug/m3 comparison scale. | Approve bounded fallback; match scale | Fitted the available county panel and transformed the coefficient for comparison. | Changed outcome specificity and geographic coverage; corrected the reported comparison scale. |
| Brazil cancer mortality | Direct + reconstructed | Pursue national coverage rather than accepting an early narrow result; search regulator and public-monitor archives beyond the default API, then retain the strongest supported covered panel. | Broaden coverage; continue source recovery | Recovered additional public mortality and exposure records and expanded the analysis beyond the initial municipality-level attempt. | Materially broadened scope; remaining coverage limits were disclosed rather than hidden. |
| Northern Italy COVID-19 | Direct + reconstructed + interpretive | After PM2.5 coverage failed, use the article's NO2 analysis as an article-supported sensitivity. Treat the article's rounded 1.00 estimates as reported null effects. | Preserve article-supported contrast; interpret null evidence | Reconstructed the available regional NO2 panel and fitted incidence and mortality models. | Changed the pollutant contrast within the article's reported analyses; affected meta-analysis classification, not the fitted values. |
| OECD COVID-19 | Reconstructed + interpretive | Continue country-level retrieval with public outcomes and covariates, retain countries passing a declared coverage rule, and classify the article's small reported estimates according to its null conclusion. | Continue; approve covered subset; interpret null evidence | Joined country outcomes, covariates, boundaries, and reconstructed exposure and fitted four event-time models. | Reduced country coverage and affected qualitative classification; it did not change fitted estimates. |

## Cross-study intervention classes

| Intervention class | Studies with documented evidence | Purpose |
| --- | --- | --- |
| Continue after a failed route | France, Sao Jose, Sao Paulo, Brazil cancer, and other prioritized completion requests | Prevented one failed endpoint, station, or download from becoming a premature global blocker. |
| Broaden geographic coverage | Italian cities, France, Brazil cancer | Challenged an analysis that had become narrower than the strongest feasible public-data panel. |
| Preserve the article's estimand | Italian cities, Northern Italy, Sao Jose | Kept distinct pollutants, outcomes, and article contrasts from being conflated. |
| Match the reported effect scale | Italian cities, US stroke | Converted native coefficients to the article's stated OR or RR contrast. |
| Approve and label a bounded fallback | Sao Jose, Sao Paulo, US stroke | Allowed a useful fit when the exact public input was unavailable while preserving the fidelity change. |
| Interpret published evidence | OECD, Northern Italy | Applied the article's own positive or null conclusion during meta-analysis. |

## Limits

This retrospective ledger cannot support a claim of zero or precisely counted
researcher interventions. It supports the narrower claim made in the paper:
the campaign used AERIS with researcher review, and that review supplied sparse
scientific judgment rather than retrieval code, source routes, exposure values,
or fitted answers. The zero-intervention campaigns were run separately under
the frozen self-driving protocol.

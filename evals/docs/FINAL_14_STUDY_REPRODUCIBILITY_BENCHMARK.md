# AERIS Reproducibility Benchmark

## Purpose

This document records how we selected the studies that AERIS can be asked to rerun **now**: public outcome data can be retrieved without an account, request, agreement, or collaborator; the paper provides the necessary study design; and the pollutant exposure can be rebuilt with AERIS-compatible public monitoring data, allowing a documented source substitution where needed.

This is a feasibility benchmark. It does not yet report AERIS executions or agreement between reproduced and published effect estimates.

## Candidate selection and execution outcome

The selection pipeline produced 14 execution candidates with documented data
routes, plus one separately labeled coverage-limited candidate. Execution
produced nine fitted same-pollutant reconstructions for quantitative
meta-reproduction. China, Israel, Taubate, Alaska, and Argentina were removed
after documented runs because the required exposure or outcome data were not
sufficient. `../benchmark/execution_outcomes.csv` records each decision.

| PMID | Study | Outcome route |
| --- | --- | --- |
| 33585383 | *COVID-19 Higher Mortality in Chinese Regions With Chronic Exposure to Lower Air Quality* | Public GitHub CSV |
| 38182658 | *Association of air pollution and weather conditions during infection course with COVID-19 case fatality rate in the United Kingdom* | UK government COVID download |
| 39377000 | *Inequities in air pollution on stroke mortality among Older Americans: a U.S. nationwide analysis* | CDC WONDER public query/export |
| 33398753 | *Effects of the spread of COVID-19 on public health of polluted cities* | Mendeley Data workbook |
| 33484722 | *Effects of chronic exposure to ambient air pollutants on COVID-19 morbidity and mortality: a lesson from OECD countries* | WHO COVID CSV |
| 34260961 | *Effects of chronic exposure to ambient air pollutants, demographic, and socioeconomic factors on COVID-19 morbidity: the Israeli case study* | Israel government municipality CSV |
| 34488764 | *Impact of long-term exposure to PM2.5 and temperature on coronavirus disease mortality: observed trends in France* | French government department-level COVID data |
| 36197352 | *Association between exposure to air pollutants and hospitalization for SARS-CoV-2: an ecological time-series study* | DATASUS public query/export |
| 36383802 | *Exposure to air pollution and hospitalization due to COVID-19 in São José dos Campos, Brazil* | DATASUS public query/export |
| 34004167 | *Effects of short- and long-term exposure to atmospheric pollution on COVID-19 risk and fatality: analysis of the first epidemic wave in northern Italy* | Italian Civil Protection GitHub data |
| 33227571 | *Cluster of climatic and pollutant characteristics increases admissions for acute myocardial infarction: analysis of 30,423 patients in the metropolitan area of São Paulo* | DATASUS SIH/SUS public query/export |
| 38249516 | *Spatial proximity to wildfires as a proxy for measuring PM2.5: a novel method for estimating exposures in rural settings* | BRFSS public data |
| 39689648 | *An ecological study on the correlation between sanitary vulnerability and air pollution with COVID-19 pandemic burden* | Argentina public COVID data |
| 38788590 | *Cancer mortality risk from short-term PM2.5 exposure and temporal variations in Brazil* | DATASUS public data transfer |
| 34389545 | *Excess of COVID-19 cases and deaths due to fine particulate matter exposure during the 2020 wildfires in the United States* | Public author GitHub repository; coverage-limited AERIS candidate |

Exact links, data-field evidence, analysis specifications, and implementation needs are in `reproducibility_audit_queue.csv`.

## Corpus and discovery record

The starting corpus was the frozen **18,919-record** deduplicated PubMed/OpenAlex corpus in `../data/study_corpus.csv`. This benchmark was constructed through two complementary routes, then a common AI-assisted reproducibility audit.

### Route A: strict public-data and public-source review

1. The strict route defined outdoor ambient criteria pollutants, human-health outcomes, source-native PubMed/OpenAlex retrieval, deduplication, and a public-data-route screen.
2. It then validated the retained studies for outcome data, time, geography, covariates, and a bounded primary analysis.
3. A public-source rescue pass included studies that assemble their inputs from named public systems rather than share a single merged analytic file.
4. This route produced a nine-study seed benchmark. Its study-level decisions are retained in `../data/reproducibility_audit_queue.csv`.

### Route B: outcome-first review

1. The same 18,919 records were routed using title/abstract metadata to organize review, not to make final exclusions. The resulting ledger is `../data/outcome_route_discovery_ledger.csv`.
2. The routing counts were: 203 `named_reusable_public_system`, 3,430 `likely_public_aggregate_outcome`, 6,251 `likely_individual_or_restricted_outcome`, and 9,035 `insufficient_metadata_for_outcome_route`.
3. Every one of the 203 named-system records received an article-level outcome-source review. It yielded 45 direct-download routes and 47 public portal/retrieval routes, for 92 outcome-access-positive records. The full ledger is `../data/public_outcome_downloadability_ledger.csv`.
4. All 92 received a second article-level review for exposure scope and retrieval mechanics. Seventeen concerned ambient pollution or wildfire smoke; 13 had an unauthenticated public outcome route. The complete review is `../data/ambient_scope_and_access_review_queue.csv`.

### Merge and final manual check

1. The nine Route A studies and 13 Route B studies shared one study (PMID 36383802), producing **21 distinct studies**.
2. Every one of the 21 received an AI-assisted paper-and-source review. The review verified: actual outcome retrieval; outcome definition; date key; geographic key; public covariates; primary analysis specification; and the feasibility of rebuilding the pollutant exposure with AERIS-compatible public monitoring data. The protocol is `REPRODUCIBILITY_AUDIT_PROTOCOL.md`.
3. Selection results: 14 `rerunnable_with_adapter`, six `not_rerunnable`, and one `unresolved`. The 14 records entered execution. Nine yielded fitted same-pollutant reconstructions; five were removed after execution because their required exposure or outcome data were insufficient. `../benchmark/execution_outcomes.csv` records the final status. The unresolved study is the Colombia COVID study: its paper identifies the INS source and fields, but its historical July 2020 export/query has not yet been recovered.

## Decision rules

### Include as an execution candidate

A study is included only when all of the following are true:

1. It estimates a human-health association with outdoor ambient criteria pollutants, wildfire smoke, or desert dust.
2. The original outcome source is named in the paper and can be used now without a login, registration, request, agreement, approval, or collaborator.
3. The public source provides, or a documented public query can provide, the reported outcome and its required time and geographic keys.
4. The paper specifies a primary analysis and its non-exposure covariates sufficiently to implement it.
5. AERIS can reconstruct an appropriate ambient pollutant exposure from public monitoring data. Where the original study used a different exposure product, the rerun must state that it is a source-substitution replication.

### Exclude or hold

- A restricted outcome source, absent public geography/time key, or missing/ambiguous primary analysis is excluded from the runnable-now benchmark.
- A named source without a recovered current or archived retrieval route is `unresolved`, not excluded for lack of a source name.
- Lack of author code or a preassembled analytic dataset is not a reason to exclude a study.

## Reproducing this selection

Run the publication-package validator from this directory:

```bash
python3 ../scripts/build_final_manifest.py
```

The saved review files are the evidence record. An independent reviewer should re-check their URLs because public dashboards, portals, and archives can change.

## AI-review provenance

The article-level reviews were conducted by Codex subagents based on GPT-5, not human reviewers. The 203-paper outcome-source review was accessed on 2026-08-13; the 92-paper ambient/access review and the 21-study reproducibility audit were accessed on 2026-08-14. “Article-level review” means the agent was instructed to read the paper's Methods/data-availability material and the cited original source, rather than decide from a metadata heuristic. These AI-assisted decisions require human verification before publication.

## Limits of the selection process

This is not a claim that the dual discovery strategy exhaustively identified every reproducible study in the 18,919-record corpus. Route B has so far completed article-level source review only for the 203 high-precision named-system records; the 3,430 likely-public-aggregate records remain a separate review queue. The benchmark is therefore a transparent, currently runnable set, not a population estimate of all reproducible ambient-health studies.

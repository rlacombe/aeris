# AERIS Source-Substitution Reanalysis Evaluation

This package records the AERIS public-health source-substitution evaluation.
Each study begins with a published analysis, its public outcome route, and its
reported study design. AERIS independently reconstructs the ambient-exposure
record from supported public sources and carries it through a reviewable
analysis. The study folders preserve the code, prompts, manifests, and results
needed to inspect that work.

The package deliberately excludes the articles' air-pollution values and
original exposure datasets. Agreement with the published conclusion and effect
estimate is the robustness check for the reconstructed workflow.

## Contents

- `literature-search/`: PubMed and OpenAlex retrieval scripts, the frozen
  protocol, and the article-and-source review prompt.
- `docs/DATA_COLLECTION_PROMPT_SUMMARY.md`: concise reconstruction of the
  study-identification and source-review instructions.
- `docs/REPLICATION_PROMPT_SUMMARIES.md`: shared and study-specific
  source-substitution instructions for all 15 execution attempts.
- `docs/CODE_INVENTORY.md`: primary executable entry points for every study.
- `docs/REVIEW_PROVENANCE.md`: the GPT-5 Codex review model, dates, and scope.
- `docs/FINAL_14_STUDY_REPRODUCIBILITY_BENCHMARK.md`: screening counts,
  eligibility rules, and exclusions from the 18,919-record corpus.
- `benchmark/`: selected-study registry, execution outcomes, effect-comparison
  ledgers, and summary metrics.
- `replications/`: one directory per attempted study. Each contains executable
  public-input, AERIS-exposure, and fitting code, plus a `README.md`,
  `REPLICATION.md`, or `RESULT.md` explaining the target and outcome.
- `OPENAQ_ATTRIBUTION_MANIFEST.md` and `OPENAQ_ATTRIBUTION_MANIFEST.csv`:
  upstream air-quality monitoring provider and license audit across all nine
  fitted reanalyses.
- `RESEARCHER_INTERVENTION_LEDGER.md`: study-by-study accounting of researcher
  steering and source-selection decisions in the interactive runs.
- `controls/self-driving/`: three zero-intervention autonomous AERIS campaigns,
  run registries, manifests, transcripts, and effect-comparison summaries.
- `controls/raw-agents/`: three matched ablation campaigns run with the same
  coding agent and model without AERIS, including all 27 attempt records.
- `scripts/`: scripts that calculate the benchmark summaries and figures.

## Reproduce a study

Read the selected study's `README.md` first. It gives the public sources,
required AERIS environment, command order, source substitutions, and result
location. Source manifests record retrieval URLs and checksums where downloads
are used. Raw public downloads, API caches, and derived panels are intentionally
excluded from this repository; the scripts retrieve or rebuild them.

## Scope

The benchmark contains 15 documented execution attempts. Nine yielded fitted
same-pollutant source-substitution reanalyses. The remaining attempts preserve
the observed data-coverage or access blocker. This record makes the successes
and the limits of public-source exposure reconstruction inspectable.

# Review Provenance

## What “manual review” means here

The article-level decisions in this package were made by **AI agents**, not by human reviewers. “Manual” means that an agent reviewed each assigned paper and its cited original data source individually, rather than making the decision from a title, abstract, or keyword heuristic alone.

## Model and dates

| Review stage | Records | Reviewer | Source access date |
| --- | ---: | --- | --- |
| Outcome-source review | 203 | Codex subagents based on GPT-5 | 2026-08-13 |
| Ambient-scope and retrieval-mechanics review | 92 | Codex subagents based on GPT-5 | 2026-08-14 |
| Full reproducibility audit | 21 | Codex subagents based on GPT-5, followed by a direct-methods correction for the Colombia study | 2026-08-14 |

The agents were instructed to read the paper's Methods and data-availability material, identify the original outcome source, and inspect the cited download, API, or query route. They recorded a short evidence statement and URL in the relevant CSV row.

## Important limitation

These are AI-assisted review decisions. They should be independently checked by a human before publication, and every external route should be rechecked immediately before an execution run because public dashboards, archives, and URLs change.

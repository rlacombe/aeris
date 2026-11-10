# Data-Collection Prompt Summary

## Status

This document reconstructs the instructions used to build the AERIS evaluation
corpus. It summarizes the project conversation, the saved review prompt, and
the recorded protocol. It is not a verbatim chat transcript.

The executable article-review prompt is
[`literature-search/prompts/article_source_review.md`](../literature-search/prompts/article_source_review.md).
The model, review dates, and scope are recorded in
[`REVIEW_PROVENANCE.md`](REVIEW_PROVENANCE.md).

## Corpus discovery

Search PubMed and OpenAlex for recent public-health studies that associate an
ambient air pollutant with a health outcome. Restrict the publication period to
the final five years at the time of search. Deduplicate records by DOI, then by
normalized title, year, and first author when a DOI is unavailable. Preserve
the full deduplicated corpus and every query.

Include studies of outdoor ambient criteria pollutants, wildfire smoke, or
desert dust. Do not require an individual address: a study may use participant
locations, postal areas, municipalities, counties, administrative areas, or
another stated geographic key.

## Article and source review

For each candidate, read the Methods and data-availability material. Inspect
the original outcome source named by the paper. Do not infer data availability
from the title, abstract, publisher page, or a generic claim that data are
public.

Record the following evidence:

1. Citation and persistent identifier.
2. Pollutant, exposure type, health outcome, study dates, and geography.
3. The named outcome source and a direct download URL, public portal route, or
   reproducible public query.
4. Whether retrieval requires a login, request, agreement, approval, or
   collaborator.
5. Whether the public route supplies the date and geographic keys needed for
   the reported analysis.
6. The primary analysis and non-exposure covariates.
7. Whether AERIS can construct an independent ambient exposure for the stated
   pollutant, place, and period.
8. A retain, exclude, or unresolved decision with one evidence-based reason.

The review is agent-assisted rather than keyword-only. Each decision must be
grounded in the article and the primary source. Record uncertainty plainly.

## Execution eligibility

Retain a study for an execution attempt when all of the following hold:

1. It studies an ambient outdoor pollutant, wildfire smoke, or desert dust.
2. The paper identifies the outcome source.
3. We can retrieve the outcome now without credentials, a request, agreement,
   approval, or a collaborator.
4. The retrieved route supplies usable outcome, date, and geographic fields.
5. The paper provides enough analytic detail to build a bounded reanalysis.
6. AERIS can attempt an independent public-source exposure reconstruction.

The final execution audit may remove a retained study when the required panel
cannot actually be constructed. Preserve that result and its evidence; do not
rewrite the earlier screening decision.

## Required audit products

Keep the deduplicated corpus, query log, review ledgers, article-review
evidence, source URLs, decision reasons, and final execution outcome. The
release package preserves these products in `literature-search/`, `data/`, and
`benchmark/`. The full selection narrative is in
[`FINAL_14_STUDY_REPRODUCIBILITY_BENCHMARK.md`](FINAL_14_STUDY_REPRODUCIBILITY_BENCHMARK.md).

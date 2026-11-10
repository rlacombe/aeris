# Literature Search and Review Materials

This directory contains the publication-facing materials for the AERIS
source-substitution reanalysis search. It records the protocol, retrieval
scripts, title/abstract screen, and the prompt used for article-level source
review. The committed ledgers in `../data/reviews/` are the results of this
workflow.

[`prompts/article_source_review.md`](prompts/article_source_review.md) is the
executable review prompt. [`../docs/DATA_COLLECTION_PROMPT_SUMMARY.md`](../docs/DATA_COLLECTION_PROMPT_SUMMARY.md)
explains the broader instruction sequence used to create the corpus and audit
the public data routes.

## Order of operations

1. Run the PubMed and OpenAlex retrieval scripts using the protocol's frozen
   date range and queries.
2. Deduplicate the records and retain the raw retrieval responses.
3. Apply the title/abstract screen to organize article-level review.
4. Ask the review agent to read the Methods and data-availability material and
   inspect the named primary outcome source.
5. Record one review row per article, including the source URL, access route,
   time key, geographic key, model information, decision, and reason.
6. Publish the full candidate ledger and execution outcome for every study that
   enters the final audit.

The scripts retain the original retrieval logic. Before release, refactor their
project-specific paths into documented command-line arguments and archive the
returned metadata alongside the committed ledgers.

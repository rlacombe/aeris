# Independent public-data reanalysis

Read the supplied article and supplementary material. Reconstruct its principal
air-pollution analysis as closely as publicly accessible data permit.

You must independently determine the target health outcome, pollutant, study
period, geography, statistical unit, covariates, exposure assignment, and model
from the article. Find and retrieve the public health-outcome data and other
required public inputs. Construct the air-pollution exposure from an independent
public source. Do not use pollution values, exposure tables, analysis code, or
derived exposure fields released by the article's authors. You may use an
author-designated public table for health outcomes and covariates after writing
a sanitization step that drops all pollution, exposure, fitted-value, and
derived analysis columns before inspection or modeling. Save the retained and
dropped column names.

Fit the principal comparison only when the reconstructed panel supports it. If
it does not, report the blocker and preserve the evidence needed to verify that
conclusion. Do not invent data, silently relax coverage, or report a model that
failed to execute.

Work without human scientific assistance. You may retry transport and
infrastructure failures under the supplied retry policy. Record every source,
retrieval, geographic or temporal substitution, outcome substitution,
covariate omission, coverage decision, and modeling decision.

Write all code and outputs under `/output`. Produce the files required by the
output schema. At minimum, write `/output/result.json` matching the supplied
agent-output schema, `/output/source_manifest.json`, `/output/decision_log.md`,
`/output/blocker_ledger.md`, the executable analysis code, and any exposure
table, analysis panel, and model output used for the estimate. End with a
concise machine-readable run summary. Include the artifact produced by
`record_reanalysis_fidelity` as `fidelity_record` in `result.json`.

For a fitted result, report every comparison contrast declared in the locked
study contract and identify one as primary. For each, report the model's native
coefficient and confidence interval. Also transform it to the declared
comparison scale as a positive OR, RR, or outcome ratio. State the exact
contrast and transformation in code. When the native result is already an OR
or RR, repeat it in both representations.

For every fitted result, populate `analysis_diagnostics` from the executable
analysis: observations and estimated parameters; unique exposure and outcome
values; joined and unmatched row counts; confirmation that the declared
contrast transformation was checked in code; and every locked principal
variant reported by the fit. Do not infer these values from the publication.

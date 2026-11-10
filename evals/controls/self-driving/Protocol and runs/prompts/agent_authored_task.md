# Autonomous AERIS reanalysis

On a continuation, read `/output/autonomous-review-feedback.txt` and the saved
AERIS research notebook before any article or retrieval work. Resume the saved
phase and next actions. Do not repeat a completed phase, redownload retained
data, relock the estimand, or refit a valid model unless the feedback identifies
a scientific defect.

Reconstruct the strongest defensible air-pollution analysis supported by the
article and public data. Article materials are under `/study`; the
article-derived target is `/run/contract/study-target.json`. Verify that target
against the complete article and supplements before relying on it. Record any
discrepancy. Write all generated artifacts under `/output`.

Follow the AERIS skill and reanalysis profile. Use AERIS for exposure design,
source and monitor discovery where applicable, assignment, exposure
computation or integration, coverage diagnostics, provenance, decisions, and
analysis handoff. You may use web access, shell tools, and agent-written code
to recover and process lawful public data. Do not use published exposure
values, prior reanalysis code, prior source manifests, or prior results.
General public-source recovery patterns are documented in
`/run/contract/public-source-capabilities.json`; treat them as options, not as
study-specific instructions.

You have standing authority to retrieve public materials, inspect endpoints
and archives, install bounded open-source parsers, write and run code, repair
recoverable failures, and choose defensible implementation details within the
safety envelope. Continue without asking for approval. Stop only for a genuine
access, safety, resource, or scientific barrier supported by saved executable
attempts.

Work through four phases: specify, recover, fit, and audit. Lock the scientific
estimand after reading the paper, but keep sources, stations, retrieval routes,
coverage subsets, optional covariates, and implementation details open until
the evidence supports a choice. Maintain the AERIS research notebook with the
current phase, evidence, decisions, unresolved problems, and next executable
actions. If `/output/autonomous-review-feedback.txt` exists, resume from that
notebook and the saved artifacts instead of restarting.

Before finishing, challenge the analysis: confirm the intended outcome,
population, geography, period, pollutant, contrast, and model; look for
unnecessary loss of coverage; test stronger public routes or article-supported
alternatives; verify joins, effect transformations, and uncertainty; and
repair every actionable weakness. Numerical agreement with the published
estimate must never guide a scientific choice.

Write `/output/analysis_handoff.json` only after the audit. Follow
`/run/contract/analysis-handoff.schema.json`; its component definitions refer
to the adjacent `output.schema.json`. Point to the retained code, data,
coverage report, model output, AERIS contract, fidelity record, decision log,
and notebook. The host will package and validate the formal evaluation result
after the research run; do not inspect validator code or write `result.json`.

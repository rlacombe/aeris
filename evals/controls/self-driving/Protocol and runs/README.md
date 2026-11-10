# Autonomous AERIS evaluation

This directory contains the frozen, anonymous materials for the autonomous
evaluation reported in the paper. It excludes credentials, downloaded article
files, public-source payloads, and the large raw run archives.

## Contents

- `frozen/aeris-self-driving/`: exact AERIS source snapshot used by the agent.
- `config/`: network, retry, safety, and self-driving policies.
- `prompts/`: clean-room task instructions.
- `schemas/`: structured handoff and run-manifest contracts.
- `scripts/`: clean-room runner, packaging, validation, and safety checks.
- `analysis/`: results from all three frozen campaigns, their study- and
  contrast-level comparisons, compact records for all 27 AERIS and 27 raw-agent
  attempts, and the Sao Paulo repeatability summary.
- `AERIS_SELF_DRIVING_FREEZE.md`: model, container, commit, prompt sizes, and integrity hashes.

## Evaluation design

Each study ran in a fresh Docker workspace with Codex CLI 0.155.1, GPT-5.6
Terra, and medium reasoning. The agent received the article-derived scientific
target and neutral article bundle. It received no prior reanalysis code, source
routes, manifests, exposure values, or results. Publication values were joined
only after each run was final.

The three nine-study campaigns produced 23 fits in 27 attempts with zero
scientific intervention. `analysis/AERIS-self-driving-study-results.csv` contains every
study-level outcome, and `analysis/AERIS-self-driving-summary.json` records completion,
runtime, and token use by campaign. The effect comparison includes only
contrasts that could be normalized directly to the published pollutant and
contrast. Run `python analysis/score_aeris_self_driving_effects.py` to regenerate the
contrast-level CSV and agreement summary from the frozen comparison map.

The matched raw-agent condition produced 3, 3, and 1 fitted effects across its
three campaigns. `analysis/raw-agent-three-campaign-summary.json` records the
aggregate metrics. Per-attempt records and campaign ledgers are in
`analysis/raw-agent-run-registry/`.

## Large artifacts

The supplement retains each run's transcript, generated code, result, source
manifest, and validation evidence. It omits bulky downloaded public datasets
and article files that cannot be redistributed. Source manifests and transcripts
record how those inputs were retrieved.

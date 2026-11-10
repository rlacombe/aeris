# Autonomous AERIS AERIS-self-driving freeze candidate

## Purpose

This configuration evaluates whether AERIS can complete public-health source-substitution reanalyses without scientific intervention. The harness was revised from general failure modes observed during development. No prior replication code, source routes, manifests, exposure values, or results enter a clean run.

## Frozen configuration

- AERIS commit: `674c6b8ede29f22d7cdb4dfea401ccfdcb0b17f1`
- Container tag: `aeris-scientific-self-driving:2026-09-25-v8-4`
- Container digest: `sha256:1c4bd461fa4df699684e10077cafe40926e7ae25a0c9baea217a613d04993a1a`
- Host: Codex CLI, GPT-5.6 Terra, medium reasoning
- Human scientific interventions: zero
- AERIS core skill: 446 words
- Reanalysis profile: 1,397 words
- Clean-room task: 404 words
- Self-driving policy: 646 words
- Retry policy: 727 words

The host may retry incomplete or invalid handoffs from retained state. Host validation never supplies study-specific routes, analytic choices, estimates, or desired answers.

## Sentinel gates

| Study | Status | Autonomous result | Published result | Notes |
|---|---|---:|---:|---|
| São Paulo AMI | Completed fit | 1.145 (1.102–1.190) | 1.090 | 39/39 municipalities; 967 overlapping days; 29 stations |
| Italian cities | Completed fit | 1.150 (0.894–1.480) | 1.760 | 32/55 cities; reduced coverage recorded explicitly |
| OECD COVID-19 | Completed sensitivity | 1.017, 1.005, 0.985, 0.926 | 1.020, 1.030, 1.020, 1.009 | 36/36 countries; four day-60/day-80 case/death contrasts |

Across these six comparisons, the median absolute log-effect difference is 0.042, or a 1.043-fold separation on the ratio scale. The mean is 0.104 because the Italian-cities estimate differs materially from the published result.

Every sentinel retained a fitted contrast, executable analysis, source evidence, and exposure data. Computational validity determines completion. Coverage, fidelity, and structured-provenance findings are reported separately as audit warnings and do not erase a fitted reanalysis.

## Freeze decision

The scientific instructions are frozen for the final Codex campaign. Subsequent changes may repair execution or validation defects, but must not add study-specific routes, thresholds, models, or target values. Campaign results will be reported as observed, including blockers, reduced-fidelity fits, and numerical disagreement.

## Host integrity hashes

- `schemas/run_manifest_v2.schema.json`: `a3614d00a8967d45bd136a8bb8a246fc64f0858cad47552b111b16a765758f8e`
- `scripts/package_reanalysis_result.py`: `402d3f3407df73d6cb41d121d4a9b112592377fc8db0bb218a99a2c465f0773f`
- `scripts/run_codex_self_driving.sh`: `2714cab78ba71c4442ca3b09f431513c2c18f3687cc4fc9b0367fae369f27631`
- `prompts/agent_authored_task.md`: `2caed9ade1e0561fb013546f7ed93ba8ddf836f4ecd73ffc675391971efa3649`
- `scripts/validate_autonomous_result.py`: `c3fdeeeccd4685f4d7ed7ed92ddf9a7dcd97e660c8badb2979b8c56145fffdbd`
- `scripts/scan_artifacts_for_secrets.sh`: `97cb0f096c98a1dfc43b786942cf99a4636e7196b551fbdca9168051547b8c23`

The host-only changes after the scientific freeze normalize equivalent OR/RR
labels, recognize JavaScript as executable analysis code, and avoid treating
`Risk-Short-Term` in a public article URL as an API credential. They do not
change the agent instructions, scientific target, retrieval policy, or model.
The runner also resolves the optional credential file from `AERIS_ENV_FILE` or
the current user's home directory instead of a developer-specific path.

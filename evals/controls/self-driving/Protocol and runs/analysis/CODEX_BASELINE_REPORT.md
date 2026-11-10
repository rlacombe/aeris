# Unaugmented Codex ablation

## Result

Codex without AERIS completed a fitted reanalysis for 3 of the 9 studies
(33%). It stopped with documented blockers for the other 6. Each task had
previously produced a fitted result during the original AERIS-assisted
campaign, so these stops count as operational failures on known-feasible
reanalysis tasks.

The ablation used Codex CLI 0.155.1 with GPT-5.6 Terra at medium reasoning.
Every run started in a clean container, received the article bundle and common
task contract, and had public network access. No run received AERIS code,
instructions, tools, prior reanalysis code, prior results, or scientific help
from a researcher.

| Study | Outcome | Published ratio | Codex ratio (95% CI) |
| --- | --- | ---: | ---: |
| Italy COVID-19 | Fit | 1.76 | 1.64 (1.43-1.87) |
| OECD COVID-19, day-80 cases | Fit | 1.02 | 1.08 (0.94-1.23) |
| UK COVID-19 | Fit | 1.13 | 2.50 (2.44-2.57) |
| Sao Paulo AMI | Stopped | - | Pollution series and exact outcome definition unresolved |
| Northern Italy COVID-19 | Stopped | - | Agent declined inference from two regional clusters |
| France COVID-19 | Stopped | - | Historical PM2.5 raster and adjustment panel unresolved |
| Sao Jose admissions | Stopped | - | Outcome download timed out; selected exposure source returned nulls |
| Brazil cancer mortality | Stopped | - | Historical mortality microdata retrieval failed |
| US stroke mortality | Stopped | - | Target outcome and national pollution coverage unresolved |

The three ratios are expressed on the published contrasts. Italy's fitted
log-log coefficient is converted to a ratio per doubling. The OECD coefficient
is exponentiated per 1 microgram/m3. The UK odds ratio per 1 microgram/m3 is
raised to the tenth power for comparison with the published 10-microgram/m3
contrast.

## Effect agreement

All three completed fits preserved the article's qualitative conclusion: two
positive associations and one estimate with no evidence of an association.
The median absolute difference between their log-transformed effect estimates
and the published estimates was 0.073; the mean was 0.307. Their geometric mean
reconstructed-to-published ratio was 1.295. The UK
estimate accounts for the gap between the median and mean: its reconstructed
odds ratio was 2.50, compared with 1.13 in the article.

These effect metrics describe the three tasks the baseline completed. They do
not compensate for the six missing fits and should never be reported as a
nine-study estimate of accuracy.

## Blocker audit

The six stopped runs produced evidence for the limitations they encountered.
Their chosen retrieval or modeling paths were incomplete, however, because the
original AERIS-assisted campaign found a path to a fitted result for every
study. This distinction captures the central failure: unaided Codex often
recognized that its current inputs were inadequate but did not find the source,
substitution, or execution path needed to finish the analysis.

The original campaign included researcher review and iterative guidance. The
current 3/9 versus 9/9 comparison therefore establishes a useful preliminary
control, while the clean, zero-intervention AERIS repetitions will isolate the
harness's contribution more directly.

## Resources and auditability

The nine runs took 3,610 seconds in total, with a median of 358 seconds per
study. They used 11,223,242 input tokens, 103,007 output tokens, and 197 shell
tool calls. Human scientific interventions were zero.

Every run retains:

- the complete JSONL agent transcript;
- generated analysis and retrieval code;
- downloaded source files and a source manifest;
- the exposure table and analysis panel;
- model output or blocker evidence;
- the decision log, structured result, and run manifest; and
- the frozen article bundle checksum and Docker image digest.

All nine structured results passed schema validation. A fresh credential-pattern
scan found no matches. Two wrappers had returned exit code 1 after their
original post-run scans; the scientific outputs and original exit codes remain
unchanged for audit.

## Reproduction

Run the summary from the repository root:

```bash
python3 iclr-2027/experiments/clean-room/analysis/audit_codex_baseline.py
```

The script regenerates `outputs/summary.json`, `outputs/study_results.csv`, and
`outputs/artifact_inventory.csv`. The inventory records the size and SHA-256
digest of every preserved run artifact.

# Blocker ledger

## B-001 — campaign disk-space policy termination

- Detected 2026-09-22T15:30:11Z.
- Evidence: `df -h /output` reported 12 GiB available on the output filesystem.
- Applicable rule: the retry policy requires at least 20 GiB free *before* a study and says that a policy termination is retained with its termination reason.
- Consequence: no further acquisition or decompression was permitted; the national 2000–2019 SIM outcome files, independent daily PM2.5, ERA5 covariates, exposure table, matched panel, and regression were not constructed.
- Scientific decision: no partial geography, period, outcome, exposure, or model was substituted; no estimate is reported.

## B-002 — article PDF endpoint (non-decisive)

- The ScienceDirect PDF endpoint returned HTTP 403 and no bytes. Its headers are retained at `logs/sciencedirect_headers.txt`.
- This is non-decisive because the supplied record, a lawful public search result, and the Monash landing page established the target. The disk guard independently terminated the run before alternative full-text retrieval could be pursued.
- Protocol deviation: the client mistakenly retried the HTTP 403 six times. The retry policy allows one attempt for other 4xx responses. This is logged in `source_manifest.json`; it did not change the scientific task or produce data.

## B-003 — health-data endpoint attempt (non-decisive)

- The DATASUS SIM directory connection timed out (0 bytes) and is documented in `logs/datasus_headers_2.txt` and `source_manifest.json`.
- No retry or source substitution was made after B-001.

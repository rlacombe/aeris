# Decision log — PMID 33227571

## Target reconstructed from the supplied citation record

| Item | Reconstructed specification | Evidence |
| --- | --- | --- |
| Outcome | Daily acute myocardial infarction admissions; in-hospital mortality was secondary | Supplied abstract (`/study/article.txt`) |
| Geography | 39 municipalities in metropolitan São Paulo, Brazil | Supplied abstract |
| Period | 2012–2015 | Supplied abstract |
| Statistical unit | Day (the reported cluster counts sum to 1,092 days) | Supplied abstract |
| Environmental variables | Temperature variation, rainfall, relative humidity, NO2, PM2.5, PM10 | Supplied abstract |
| Exposure/assignment | Hierarchical clustering of daily weather and pollutant features; monitoring aggregation/assignment not identifiable from available record | Supplied abstract |
| Principal comparison/model | Admission measures compared across three clusters; exact test/model, reference category, covariate adjustment, and all declared contrasts are not recoverable from the supplied abstract/landing page | Supplied abstract; publisher landing record |
| Reported finding | High-temperature-variation/low-humidity/high-pollution cluster: 9% higher admissions; 30.5 patients/day (IQR 25.0–36.0), P<0.01 | Supplied abstract; not reproduced |

## Preflight and stopping decision

At preflight, `df -h /output` reported 17 GB free; the byte-level repeat check recorded 15.69 GiB free in `/output/preflight_disk_check.json`. The frozen retry policy requires at least 20 GiB free **before** a study. This is a campaign-limit failure, not a transport failure; retrying requests or changing the analysis would not remedy it. Per the policy, the run terminates before public health, CETESB exposure, or INMET covariate downloads, panel construction, sanitization, or modeling.

No outcome, geography, period, covariate, exposure, or model substitutions were made. No author-derived exposure fields, code, tables, or fitted values were used.

The schema has no `policy_termination` status even though the retry policy defines that outcome. `result.json` therefore uses the closest schema-valid status, `completed_blocker`; the authoritative campaign outcome is explicitly recorded as `policy_termination_preflight` in the fidelity record and run summary.

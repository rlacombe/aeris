# Decision log — PMID 33227571

## Target reconstructed from supplied record

The supplied abstract identifies acute myocardial infarction (MI) admissions and in-hospital mortality in 39 São Paulo municipalities, 2012–2015. It reports a hierarchical cluster analysis of daily temperature variation, rainfall, relative humidity, nitrogen dioxide, PM2.5, and PM10. The comparison is admissions among the resulting environmental clusters. It reports 30,423 patients and three clusters of 218, 751, and 123 days (1,092 total), with a 9% admission increase in the high-pollution/dry/high-temperature-variation cluster.

## Data and decisions frozen before model attempt

- Outcome: public SIH-RD (DATASUS) records, principal diagnosis beginning `I21`, using `DT_INTER` as the admission date and `MUNIC_RES` for the 39 São Paulo metropolitan-region municipality stems. The RD records are monthly billing-competence data, so 2016-01 through 2016-04 were also read before restricting dates to 2012–2015. Duplicate AIH numbers were removed.
- Geography: 39 current RM São Paulo municipality names were matched to IBGE codes; SIH stores six-digit code stems, not the seven-digit IBGE code.
- Weather: Open-Meteo historical archive at -23.5505, -46.6333, daily maximum/minimum temperature, precipitation, and mean relative humidity. Temperature range was calculated as max minus min.
- Pollution: no values were taken from the authors or from author-released data. The required daily PM2.5, PM10, and NO2 series was not retrieved from an independent credential-free public source. `exposure_daily.csv` deliberately contains missing values rather than fabricated replacements.

## Retrieval evidence and retry decisions

- PubMed EFetch succeeded (HTTP 200); its SHA-256 is in `source_manifest.json`.
- The ScienceDirect full-text landing request returned HTTP 403. Under the retry policy, this other-4xx response was inspected and not blindly retried.
- The Elsevier content API returned HTTP 200 but only non-open-access metadata (`openaccess=false`), not full text.
- Direct DATASUS FTP over HTTPS stalled and HTTP connection timed out. A public SIH mirror documented as byte-identical to DATASUS was used; individual competence outcomes and request evidence are in `raw/sih_provenance.json` and `logs/request_log.json`.

## Coverage validation and stopping decision

The executed outcome/weather panel has 1,461 calendar days and all 39 units; it contains 51,689 deduplicated I21 admissions. This does not reproduce the reported 30,423 patients. Furthermore, 1,092 reported clustered days is incompatible with an inclusive 2012–2015 calendar panel. The missing full methods prevent resolving whether the authors used a different window, diagnosis/procedure definition, geographic assignment, or exclusions.

The principal model was **not run**. Ward/hierarchical clustering needs the three pollutant variables as part of its definition. Dropping them, imputing them, or fitting a weather-only cluster would be an undisclosed change to the target analysis. `model_output.json` records this as `not_run`, and `result.json` is `completed_blocker` rather than a failed or invented estimate.

# Independent reanalysis decision log

Study: PMID 34004167, “Effect of short- and long-term exposure to atmospheric pollution on COVID-19 risk and fatality.”

## Target identified from supplied article

The article models daily regional COVID-19 case and death counts for Lombardy and Veneto, 21 February–19 May 2020, with separate pollutant models. Its headline largest long-term association is SO2: mortality count ratio 5.37 per 1 μg/m³ LTAP SO2. The stated primary specification is a Poisson log-link GEE with an AR(1) working correlation and STAP, LTAP, and a lockdown indicator. No population offset is described. This run targets that SO2/mortality comparison.

## Frozen reconstruction choices

* Outcome: cumulative regional `deceduti` from the Italian Civil Protection public archive, differenced within region to form daily deaths. `totale_casi` is also differenced and retained for panel audit.
* Exposure: hourly SO2 from the public Open-Meteo air-quality endpoint, assigned to a regional-capital grid cell (Milan for Lombardy; Venice for Veneto), averaged to calendar days. This source is independent of the authors and none of the authors' pollution values, tables, code, or derived data were used.
* LTAP: the article does not specify enough detail to recreate its aggregation exactly. The disclosed substitute is each assigned series' mean over 2013-01-01–2020-05-19.
* Lockdown: one on/after 2020-02-22, as explicitly defined by the article.

## Coverage decision

The outcome archive's first regional observation is 2020-02-24. A daily incident count cannot be derived for that first observation, so the panel is restricted prospectively and transparently to 2020-02-25–2020-05-19: 85 of the article's 89 dates, for each of two regions (170 rows). No missing days within this retained range were imputed.

## Modeling decision and blocker

No primary GEE was fitted and no effect is reported. The scientific comparison is a long-term, region-level SO2 contrast, but the reconstructed study has exactly two independent regional clusters and two LTAP values. GEE's cluster-robust/sandwich inference is not defensible with two clusters; a numerical coefficient or confidence interval would falsely imply reliable independent replication. The reduced outcome coverage and the necessarily substituted exposure assignment are separately preserved in the artifacts. This is a completed blocker, not a failed model.

## Retrieval record

The executable script applies the supplied transport retry schedule to its HTTP GET requests and writes every actual request attempt, status, byte count, and delay to `request_log.json`. The run used no retries unless the log says otherwise. Source hashes and local retained inputs are in `source_manifest.json`.

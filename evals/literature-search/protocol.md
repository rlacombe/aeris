# AERIS Replication Benchmark: Agent-Assisted Systematic Literature Search

## Purpose and scope

This protocol identifies published environmental-health studies that can be independently
reproduced with AERIS. The benchmark question is whether AERIS can take public study
data containing health outcomes, covariates, geography, and time; construct a substitute
ambient-pollution exposure record from public OpenAQ observations; and execute the
study's declared analysis for comparison with its reported result.

This is an agent-assisted systematic literature search to construct an auditable benchmark
corpus. It is not a meta-analysis and will not pool health-effect estimates or
estimate the prevalence of reproducible studies. All records returned by every executed,
pre-specified database query will be exported, deduplicated, and screened under this
protocol. Exact searches, dates, raw exports, candidate links, and eligibility decisions
are retained so the selection can be inspected and extended. As with any automated review,
database indexing and model-assisted screening may still miss eligible studies; this
limitation will be stated without weakening the full-scope search procedure.

The frozen publication-eligibility window is 1 January 2020 through 30 June 2026.
The primary analysis observation window must have more than half of its stated duration on or after
1 January 2015, and must not extend beyond 30 June 2026. For a study reported only in whole years,
the same rule is applied to the inclusive calendar-year interval. A report is the unit of
identification and screening. A study is the unit of the final benchmark; multiple reports
using the same underlying data and analysis count as one study.

The temporal rule retains modern public-monitoring studies while preserving established
open-data replications with observations beginning before 2020. Actual station, pollutant,
and time coverage is not a selection gate; it is measured and reported during each AERIS
replication.

## Eligibility framework

### Rapid scope screen

The first-pass filter is intentionally limited to three questions. Retain a report when
the answer is `yes` or `uncertain` to every question; exclude it only when a failure is
clear from the title, abstract, or readily available methods metadata.

1. **Ambient background exposure:** Does the study use outdoor ambient air quality from a
   public/government/reference monitoring network or comparable public background source?
   Exclude indoor-only, occupational-only, wearable-only, personal-sensor-only, and
   private or study-specific sensor-network exposures.
2. **Criteria pollutant:** Does the study include one or more of PM2.5, PM10, NO2, NOx,
   O3, SO2, or CO? Exclude studies limited to exotic pollutants, such as BTEX, metals,
   pesticides, PFAS, or source-specific chemical mixtures without a criteria pollutant.
3. **Observation window:** Does more than half of the stated primary analysis period occur
   on or after 1 January 2015, and does it end no later than 30 June 2026? Exclude only when
   the reported period clearly fails this rule; retain an incompletely reported period for the
   feasibility screen.

Human health outcome is supplied by the bibliographic query and is not an additional
first-pass exclusion gate. Reviews, protocols, and laboratory-only papers may be removed
by a simple document-type flag, but no public-data, analysis-model, or OpenAQ requirement
is applied at this stage.

### Replication-feasibility screen

Apply this second screen only to the retained in-scope corpus, not to every broad
bibliographic record. A study enters the replication benchmark candidate set only when
all of the following can be established from the paper, supplement, repository, or
author-linked data record:

1. **Open-access report:** The article and its essential methods/supplements are publicly
   readable without institutional login, payment, or author request.
2. **Downloadable study inputs:** Outcome data and required covariates are publicly
   downloadable
   without an application, institutional agreement, payment, or manual author approval.
   Public aggregate administrative data are eligible. De-identified individual-level data
   are eligible only when their documented release includes the geographic and temporal
   anchor needed for exposure assignment.
3. **Usable geographic and temporal anchor:** The released inputs, or a documented public
   route to reconstruct them, provide the geographic and temporal information needed by
   the study design. A geographic anchor may be a household address, coordinates, ZIP or
   postal code, census tract, locality, district, county, city, or other reported area;
   it need not be a row-level coordinate. A temporal anchor may be an event date,
   observation year, enrollment period, follow-up interval, or stated exposure window;
   it need not be a daily timestamp. Both must be sufficiently resolved for the study's
   declared exposure definition.
4. **Public outdoor monitoring exposure:** The study concerns outdoor ambient criteria
   pollutants measured by a public environmental monitoring network or another documented
   public AERIS source. Exclude private, study-specific, occupational, indoor, wearable,
   satellite-only, modeled-only, or chemical-component/source-apportionment exposure
   constructs. Wildfire-attributed PM2.5 is eligible when AERIS can construct it from a
   documented public source and frozen attribution rule. The authors' precomputed exposure
   column and analysis code are never AERIS inputs.
5. **Primary pollutant analysis:** At least one criteria pollutant is a primary analytic
   exposure with a reported numerical health result, rather than only an adjustment,
   sensitivity, or descriptive variable.
6. **Reproducible analysis specification:** The report states enough of the analysis to
   implement its primary result independently: outcome, analytic population/units,
   exposure window and scale, model family, primary adjustment set or a clearly identified
   equivalent, and target estimand/contrast.
7. **Comparison target:** A numerical primary effect estimate, uncertainty interval or
   standard error, and its scale are reported in the paper or supplement.

### OpenAQ execution metric

OpenAQ is the common substitute exposure route. It is not required to match the original
study's source. Do not query OpenAQ before selecting a study. During an executed
replication, record:

1. pollutant parameter and units;
2. candidate monitor identifiers and coordinates;
3. proportion of eligible area-time units with at least one valid observation under the
   pre-specified quality rules;
4. distance from each study area or representative point to the selected monitor(s);
5. temporal completeness for the requested averaging or lag window; and
6. whether the fixed nearest-monitor/IDW policy can assign exposure without study-specific
   exceptions.

Classify the resulting coverage as `pass`, `partial`, or `unavailable`:

- `pass`: the policy assigns exposure to the pre-specified minimum share of eligible
  area-time units and all assignment-quality thresholds are met;
- `partial`: the policy yields an explicitly reported subset or incomplete time series;
- `unavailable`: essential observations are unavailable.

Before executing the search, freeze the numerical thresholds in the project configuration
(for example, minimum coverage, maximum monitor distance, completeness requirement, and
allowed aggregation). Do not tune them after seeing agreement with published results.
Studies classified `conditional` may be retained as a sensitivity set but will not enter
the primary benchmark unless the protocol amendment is documented before analysis.

## Search sources and strategy

### Bibliographic sources

The pre-specified bibliographic sources for the current run are PubMed and OpenAlex.
All records returned by every executed query in those sources will be exported,
deduplicated, and screened; no result-limit, relevance-ranking cutoff, or convenience
sample will be used. Web of Science, Scopus, and Embase have not been executed in the
current run and must not be described as searched. They can be added only through a dated
protocol amendment with the exact query, raw export, and complete screening ledger.

For each searched database, translate the following conceptual strategy to the database's
native syntax, including controlled vocabulary where available:

```
("air pollution" OR "air quality" OR PM2.5 OR "PM 2.5" OR PM10 OR "PM 10"
 OR NO2 OR "nitrogen dioxide" OR NOx OR ozone OR O3)
AND
(health OR mortality OR morbidity OR hospitalization OR emergency OR asthma OR
 respiratory OR cardiovascular OR birth OR pregnancy OR pediatric OR mental)
AND
(2020/01/01:2026/06/30[publication date])
```

The exact, database-native search strings, date and time run, database platform/interface
or API version, field restrictions, filters, result count, export format, and raw-export
filename will be recorded in a versioned query log. The complete raw export from each
database will be retained unmodified. If a search is amended, the original search and
export will remain available; the amendment, rationale, and rerun date will be recorded.
The final appendix will reproduce every executed query exactly, rather than only the
concept blocks above.

### Supplemental discovery

After the database search and its first pass of full-text eligibility screening, conduct
backward and forward citation searching for every included report and every report that
appears eligible but lacks a verifiable public-data link. Search public repositories named
in these reports (for example Zenodo, OSF, Dataverse, OpenICPSR, and institutional
repositories) to locate linked materials. Supplemental records are screened under the
same criteria and retained in the same raw-export and screening-ledger system. Label each
record's discovery route as `database`, `citation_chase`, `repository`, or `targeted`.

No language restriction is imposed at discovery. Full-text screening requires a readable
English version or a qualified translation. Record non-English reports and translation
status rather than silently discarding them.

## Screening workflow

### 1. Collection and deduplication

Export each source's results with stable identifiers, title, authors, publication year,
abstract, DOI, PMID, and URL where available. Preserve the unmodified exports outside the
analysis ledger. Normalize DOI (lower case, remove resolver prefix), PMID, title, year,
and first author.

Deduplicate in this order:

1. exact DOI;
2. exact PMID or other source-specific stable identifier;
3. normalized exact title plus year;
4. manually adjudicated near-title match with author/year confirmation.

Retain one canonical `record_id`; list all source records and duplicate identifiers in the
ledger. Never delete duplicates without recording the retained record.

### 2. Title and abstract screen

The agent-assisted title/abstract screen assigns exactly one terminal exclusion code where
excluded, while preserving its evidence and rationale in the ledger. A deterministic
verification pass checks that every retrieved record has a decision, no required field is
missing, and no record is simultaneously retained and excluded. Any uncertain or
conflicting record is retained for full-text screening. This protocol does not claim
independent dual human review.

### 3. Full-text and artifact screen

Retrieve the paper, supplement, data-availability statement, and author-linked data
records. Screen each eligibility requirement in the stated order. Record direct landing
and download links for every required input, access date, license/terms, geographic/time
keys, and whether author-generated exposure fields have been withheld from AERIS.

Assign one primary full-text exclusion reason, using the earliest failed gate in the
following hierarchy:

1. `full_text_unavailable`
2. `methods_insufficient`
3. `no_public_outcome_or_covariates`
4. `no_usable_geography_or_time`
5. `author_exposure_required_or_private`
6. `not_ambient_background_exposure`
7. `no_reproducible_analysis_specification`
8. `no_numeric_comparison_target`
9. `other_documented`

Record all secondary issues in notes. Do not classify a study as ineligible merely because
the authors' code is unavailable; AERIS must use an independent implementation.

### 4. OpenAQ execution measurement

Run the frozen OpenAQ coverage measurement only when AERIS executes a selected study.
Preserve query parameters, raw response snapshot or content hash, API timestamps, station
list, and coverage calculation. `partial` and `unavailable` are reported replication
outcomes and do not retrospectively alter literature-screen eligibility.

### 5. Study-level consolidation and benchmark freeze

Consolidate multiple reports from the same study into one `study_id`. Choose one primary
report and preserve links to companion reports. Before executing any AERIS replication,
freeze the final benchmark list, study manifests, OpenAQ assignment policy, comparison
metrics, and analysis plans in version control. Subsequent additions are a new benchmark
version, not silent changes to the evaluated set.

## Handling unavailable material

- **Abstract but no accessible full text:** retain through the abstract stage, attempt
  publisher, preprint, institutional repository, and author-linked public copies; record
  the access attempts and classify `full_text_unavailable` if unsuccessful.
- **Full text available but data link broken:** record the URL, access date, and failure;
  classify according to the first failed public-data or exposure gate.
- **Public data under an application, DUA, login, payment, or author request:** classify
  as not public for this benchmark.
- **Data are public but locations/times are suppressed:** classify
  `no_usable_geography_or_time` unless an explicitly documented public reconstruction is
  possible without using author-only artifacts.
- **OpenAQ historical coverage has changed:** retain the raw query snapshot and report
  coverage based on the frozen retrieval date; do not retroactively alter an executed
  benchmark.

## Auditable count flow

Maintain one row per identified report in `screening_ledger_template.csv`; do not count
rows manually in prose. Broad-query totals and raw exports are the screening denominator.
Generate the manuscript flow from ledger status fields using these definitions:

1. records identified, by bibliographic source and supplemental route;
2. duplicate records removed;
3. unique records title/abstract screened;
4. records excluded at title/abstract, by exclusion code;
5. full texts sought, retrieved, and unavailable;
6. full texts assessed for eligibility;
7. reports excluded after full-text/artifact screening, by primary reason;
8. studies passing public-data and analysis-specification gates;
9. studies selected for the frozen primary replication benchmark; and
10. reports/studies completed, with OpenAQ coverage and failure status recorded as
    execution outcomes.

The flow table should distinguish database, citation-chase, repository, and targeted
discovery routes. Every reported count must be reproducible from a frozen ledger export,
identified by file hash and export date. The manuscript should state the search date,
databases actually searched, date range, exact eligibility definition, and supplemental
search methods. It should also state the normal limitation that relevant studies may have
been missed because of database coverage, indexing, or automated screening error.

## Reporting boundaries

Do not claim that the selected studies are representative of all air-pollution health
research. Do not pool health effects across studies.
Report source substitution explicitly: OpenAQ-derived exposures are evaluated against
published results, not presented as the original exposure record. The final paper must
distinguish incomplete public study data from an unsuccessful AERIS replication, including
an execution with partial or unavailable OpenAQ coverage.

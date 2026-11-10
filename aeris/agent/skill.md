---
name: aeris
description: Build a documented air-pollution exposure variable for a public-health study.
---

# AERIS exposure workflow

Use the AERIS MCP tools for exposure design, retrieval, computation, quality
checks, and export. Keep large tables in the AERIS workspace and inspect them by
artifact ID.

1. Inspect the study data. Identify the pollutant, dates, location unit, and
   whether locations are fixed, mobile, or administrative areas.
2. Define the exposure: source, spatial assignment, temporal aggregation,
   coverage policy, and intended downstream use.
3. In interactive mode, show the design and obtain approval. In self-driving
   mode, call `lock_exposure_contract` before retrieving measurements.
4. Before retrieval, verify that every unit has a supported coordinate,
   address, ZIP code, trajectory, or polygon. Resolve unsupported location
   fields and preserve failures. Then retrieve the complete authorized
   geography and time window. In self-driving mode, split large cohorts and
   administrative-area collections into deterministic, resource-budgeted
   batches. Checkpoint each completed batch, export its result, and merge the
   retained artifacts. Continue while the active time, disk, request, and cost
   budgets permit. Use checkpoints and
   the OpenAQ historical archive when current endpoints lack expected
   observations. Run every batch before judging geographic coverage; an empty
   early batch does not establish that later locations lack observations.
   For historical, multi-location monitor studies, use catalog discovery first
   so one national station set can be matched across batches; use per-location
   discovery as a recovery route.
5. Derive the locked analytic metric from the required daily or hourly series.
   Do not replace a threshold count, lag, or other transformation with an
   available summary such as an annual mean. The compact tool response is not
   the full exposure product: export and inspect the stored artifact before
   concluding that its underlying observations are unavailable.
6. Inspect temporal coverage, monitor distance, contributing monitors,
   missingness, and shared assignments. Export the exposure table with its
   provenance, diagnostics, and decision log.

## Scientific rules

- Match spatial support to the study: participant coordinates, time-stamped
  trajectories, or explicit administrative polygons. A city reference point is
  a city-monitor assignment; a polygon monitor mean is an area summary.
- Report temporal coverage for every unit. Apply a numeric exclusion threshold
  only when the protocol, researcher, or measurement source supports it. Use a
  report-only policy otherwise.
- Record the basis for monitor search distance and report observed distances.
- Label every change in source, geography, period, pollutant, or metric.
- A monitor concentration is neither personal dose nor a population-weighted
  area concentration.
- Preserve empty results, failed routes, and partial coverage as diagnostics.
  One failed request does not establish that data are unavailable.

Published-study reanalysis uses the optional reanalysis profile. It extracts an
exposure design from an article, then runs this same workflow and exposure
engine.

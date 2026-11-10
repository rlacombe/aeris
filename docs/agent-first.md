# Agent-first AERIS

AERIS is a scientific tool layer that can be used by a local CLI agent,
a terminal harness, or an MCP-compatible agent host. The host model is not part
of the exposure engine.

## Local MCP server

Install the optional MCP dependency and start the stdio server:

```bash
pip install -e ".[mcp]"
aeris-mcp
```

Use `aeris-mcp` as the command in the host's MCP configuration. If the host
does not inherit the project virtual environment, configure the command with the
absolute path to its `aeris-mcp` executable.

The MCP surface contains cohort loading, point and administrative-boundary exposure estimation, source and
station inspection, summaries, export, and decision-log retrieval. It does not expose arbitrary code execution, unrestricted file
editing, or a model provider SDK.

`get_accuweather_air_quality` retrieves AccuWeather's current/forecast
air-quality index for a coordinate when `ACCUWEATHER_API_KEY` is configured.
The result carries its source type and remains an index; it is not converted
into a pollutant concentration.

## Durable study workspace

Loading a cohort creates a study-local ``.aeris/`` workspace. The input cohort,
each completed exposure table, and each run manifest receive stable IDs. A run
manifest records the input artifact, parameters, summary, and decision log.
The existing OpenAQ SQLite cache remains separate and continues to avoid
duplicate retrievals.

Hosts should pass artifact IDs rather than full tables through model context.
The public tools ``list_artifacts``, ``describe_artifact``, ``sample_artifact``,
and ``query_artifact`` provide bounded inspection. ``query_artifact`` supports
row counts, missingness, value counts, and numeric summaries; it deliberately
does not execute arbitrary SQL or code.

`record_study_design` stores a researcher-approved record of the research
question, outcome, pollutant, location unit, exposure window, assignment rule,
and optional covariate, analysis, and sensitivity fields. Its artifact ID is
available beside the cohort and exposure artifacts. The tool validates
completeness and approval; it does not choose an adjustment strategy or assess
causal validity.

This workspace contract supports long-running and recursive host workflows.
The host may inspect artifacts in stages or delegate a bounded question, while
AERIS retains scientific inputs and outputs locally.

## Host contract

The portable instructions are in `skills/aeris/SKILL.md`. A compatible host
must follow this order:

1. Load and inspect the cohort.
2. State the pollutant, source, spatial unit and assignment rule, time window,
   aggregation, completeness policy, and planned analysis use.
3. Obtain researcher approval before calling `estimate_exposure` with
   `researcher_approved=true`.
4. Review coverage, provenance, station distance, and shared-monitor evidence.
5. Export the endpoint and preserve the decision log only when the researcher
   accepts the documented limitations.

For an administrative unit, use `estimate_boundary_exposure` and provide either
a researcher-supplied GeoJSON path or `iso3`, `adm_level`, and `boundary_name`.
The tool uses geoBoundaries for open ADM0--ADM5 geometry, then OpenAQ monitor
data. Its reported estimand is an unweighted mean of station-level means inside
the polygon. It must not be described as an area- or population-weighted
concentration.

## Host adapters

Use `./aeris.sh --agent codex`, `./aeris.sh --agent claude`, or
`./aeris.sh --agent gemini` for the supported interactive hosts. The launcher
starts a temporary MCP configuration and passes the shared AERIS instructions.
New host adapters must use `aeris.agentic.contract` rather than import a
provider SDK into the exposure engine. The contract exposes a stable JSON-schema
description through `tool_schemas()` and executes operations against a
`SessionState` through `execute()`.

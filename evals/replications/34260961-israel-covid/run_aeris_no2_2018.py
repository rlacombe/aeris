"""Reconstruct 2018 Israeli municipal NO2 with AERIS for PMID 34260961.

The paper reports NOx rather than NO2. OpenAQ's historical Israeli catalogue
contains NO2, with broad 2018 S3 coverage, so this script creates the closest
public measured-pollutant sensitivity panel. It never reads the paper's 3 km
modelled exposure surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from aeris.agent.state import SessionState
from aeris.agentic.contract import execute

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


RUN_DIRECTORY = Path(__file__).resolve().parent
ENV_PATH = Path(".env")
COHORT_PATH = RUN_DIRECTORY / "aeris_cohort.csv"
YEAR = 2018


def call(trace: list[dict], state: SessionState, name: str, **arguments: object) -> dict:
    result = execute(state, name, arguments)
    trace.append({"tool": name, "arguments": arguments, "result": result})
    return result


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(ENV_PATH, override=False)
    cohort = pd.read_csv(COHORT_PATH, dtype={"subject_id": str})
    cohort["start_date"] = f"{YEAR}-01-01"
    cohort["end_date"] = f"{YEAR}-12-31"
    annual_cohort = RUN_DIRECTORY / "aeris_cohort_no2_2018.csv"
    annual_cohort.write_text(cohort.to_csv(index=False), encoding="utf-8")

    state = SessionState()
    state.working_directory = str(RUN_DIRECTORY)
    state.config.openaq_calls_per_minute = 20
    state.config.archive_fallback_max_days = 366
    state.config.archive_fallback_max_objects = 500
    trace: list[dict] = []

    call(trace, state, "load_cohort", path=str(annual_cohort))
    call(
        trace,
        state,
        "plan_exposure",
        pollutant="no2",
        country="il",
        n_stations=1,
        temporal_resolution="daily",
        location_strategy="catalog",
    )
    estimate = call(
        trace,
        state,
        "estimate_exposure",
        pollutant="no2",
        country="il",
        n_stations=1,
        temporal_resolution="daily",
        location_strategy="catalog",
        researcher_approved=True,
    )
    output = RUN_DIRECTORY / "aeris_no2_2018.csv"
    if estimate.get("status") == "ok":
        call(trace, state, "export_results", path=str(output))
    call(trace, state, "get_decision_log")
    (RUN_DIRECTORY / "aeris_no2_2018_tool_trace.json").write_text(
        json.dumps(trace, indent=2, default=str) + "\n", encoding="utf-8"
    )
    if not output.exists():
        raise RuntimeError(f"AERIS did not create {output}; inspect the tool trace.")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

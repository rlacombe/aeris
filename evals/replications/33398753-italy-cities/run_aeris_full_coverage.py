"""Run a documented wider-area AERIS PM10 reconstruction for all 55 cities."""

from __future__ import annotations

import json

import pandas as pd

from aeris.agent.state import SessionState
from aeris.agentic.contract import execute

from run_aeris_tools import ENV_PATH, RUN_DIRECTORY, load_dotenv


SEARCH_RADIUS_METERS = 250_000
N_STATIONS = 3


def call(trace: list[dict], state: SessionState, name: str, **arguments: object) -> dict:
    result = execute(state, name, arguments)
    trace.append({"tool": name, "arguments": arguments, "result": result})
    return result


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(ENV_PATH, override=False)

    # The strict run already records the pinned GeoNames coordinates for all
    # 55 study cities. Reuse that audited cohort rather than re-download it.
    cohort = pd.read_csv(RUN_DIRECTORY / "aeris_cohort.csv")
    cohort_path = RUN_DIRECTORY / "aeris_cohort_full_coverage.csv"
    cohort.to_csv(cohort_path, index=False)

    state = SessionState()
    state.working_directory = str(RUN_DIRECTORY)
    state.config.openaq_calls_per_minute = 20
    state.config.search_radius = SEARCH_RADIUS_METERS
    trace: list[dict] = []
    call(trace, state, "load_cohort", path=str(cohort_path))
    call(
        trace,
        state,
        "plan_exposure",
        pollutant="pm10",
        country="it",
        n_stations=N_STATIONS,
        temporal_resolution="daily",
        location_strategy="catalog",
    )
    estimate = call(
        trace,
        state,
        "estimate_exposure",
        pollutant="pm10",
        country="it",
        n_stations=N_STATIONS,
        min_completeness=0,
        temporal_resolution="daily",
        location_strategy="catalog",
        researcher_approved=True,
    )
    daily_rows: list[dict] = []
    if estimate.get("status") == "ok":
        call(
            trace,
            state,
            "export_results",
            path=str(RUN_DIRECTORY / "aeris_pm10_full_coverage.csv"),
        )
        for subject_id in cohort["subject_id"]:
            daily = call(trace, state, "get_daily_data", subject_id=subject_id, pollutant="pm10")
            daily_rows.extend({"subject_id": subject_id, **row} for row in daily.get("data", []))
    pd.DataFrame(daily_rows).to_csv(
        RUN_DIRECTORY / "aeris_pm10_full_coverage_daily.csv", index=False
    )
    call(trace, state, "get_decision_log")
    (RUN_DIRECTORY / "aeris_full_coverage_tool_trace.json").write_text(
        json.dumps(trace, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps(estimate, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

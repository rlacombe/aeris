#!/usr/bin/env python3
"""Reconstruct 2007--2017 BHS-region PM2.5 through AERIS tool calls."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from aeris.agent.state import SessionState
from aeris.agentic.contract import execute

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = Path(".env")
COHORT = ROOT / "outputs" / "bhs_region_subjects.csv"


def call(trace: list[dict], state: SessionState, name: str, **arguments: object) -> dict:
    result = execute(state, name, arguments)
    trace.append({"tool": name, "arguments": arguments, "result": result})
    return result


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(ENV_PATH, override=False)
    # AERIS plotters write relative to the process directory.
    os.chdir(ROOT)
    cohort = pd.read_csv(COHORT)
    cohort["address"] = cohort["region"] + ", Alaska, USA"
    input_path = ROOT / "outputs" / "aeris_cohort.csv"
    cohort.to_csv(input_path, index=False)

    state = SessionState()
    state.working_directory = str(ROOT)
    state.config.openaq_calls_per_minute = 20
    # This is an explicit long-window sensitivity run. The default AERIS
    # archive limits remain appropriate for interactive work.
    state.config.search_radius = 1_000_000
    state.config.archive_fallback_max_days = 4_018
    state.config.archive_fallback_max_objects = 1_000
    trace: list[dict] = []
    call(trace, state, "load_cohort", path=str(input_path))
    plan = call(
        trace,
        state,
        "plan_exposure",
        pollutant="pm25",
        country="us",
        n_stations=1,
        temporal_resolution="daily",
        location_strategy="catalog",
    )
    estimate = call(
        trace,
        state,
        "estimate_exposure",
        pollutant="pm25",
        country="us",
        n_stations=1,
        min_completeness=0,
        temporal_resolution="daily",
        location_strategy="catalog",
        researcher_approved=True,
    )
    daily_rows: list[dict] = []
    if estimate.get("status") == "ok":
        call(trace, state, "export_results", path=str(ROOT / "outputs" / "wide_1000km_aeris_pm25.csv"))
        for subject_id in cohort["subject_id"]:
            daily = call(trace, state, "get_daily_data", subject_id=str(subject_id), pollutant="pm25")
            daily_rows.extend({"subject_id": subject_id, **row} for row in daily.get("data", []))
    decision_log = call(trace, state, "get_decision_log")
    pd.DataFrame(daily_rows).to_csv(ROOT / "outputs" / "wide_1000km_aeris_pm25_daily.csv", index=False)
    (ROOT / "outputs" / "wide_1000km_aeris_tool_trace.json").write_text(
        json.dumps(trace, indent=2, default=str) + "\n", encoding="utf-8"
    )
    summary = {
        "plan": plan,
        "estimate": estimate,
        "daily_rows": len(daily_rows),
        "decision_log_entries": len(decision_log.get("entries", [])),
    }
    (ROOT / "outputs" / "wide_1000km_aeris_run_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

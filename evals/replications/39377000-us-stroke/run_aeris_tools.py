#!/usr/bin/env python3
"""Run the 2019 county PM2.5 reconstruction for PMID 39377000 through AERIS."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from aeris.agent.state import SessionState
from aeris.agentic.contract import execute

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


RUN_DIR = Path(__file__).resolve().parent
SOURCE_COHORT = RUN_DIR / "aeris_cohort_2019.csv"
SAMPLE_COHORT = RUN_DIR / "aeris_cohort_2019_systematic_10pct.csv"
ENV_PATH = Path(".env")


def make_sample() -> int:
    rows = list(csv.DictReader(SOURCE_COHORT.open()))
    sample = [row for index, row in enumerate(rows) if index % 10 == 0]
    with SAMPLE_COHORT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(sample[0]))
        writer.writeheader()
        writer.writerows(sample)
    return len(sample)


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(ENV_PATH, override=False)
    n_counties = make_sample()
    state = SessionState()
    state.config.openaq_calls_per_minute = 20
    trace: list[dict] = []

    def call(name: str, **arguments: object) -> dict:
        result = execute(state, name, arguments)
        trace.append({"tool": name, "arguments": arguments, "result": result})
        return result

    loaded = call("load_cohort", path=str(SAMPLE_COHORT))
    if loaded.get("status") != "ok":
        raise RuntimeError(loaded)
    estimate = call(
        "estimate_exposure",
        pollutant="pm25",
        country="us",
        n_stations=1,
        min_completeness=50,
        temporal_resolution="daily",
        location_strategy="catalog",
        researcher_approved=True,
    )
    call("get_exposure_summary", pollutant="pm25")
    call("get_decision_log")
    if state.results.get("pm25") is not None:
        state.results["pm25"].to_csv(RUN_DIR / "aeris_pm25_2019_systematic_10pct.csv", index=False)
    (RUN_DIR / "aeris_tool_trace.json").write_text(
        json.dumps({"sample_counties": n_counties, "trace": trace}, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(estimate, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

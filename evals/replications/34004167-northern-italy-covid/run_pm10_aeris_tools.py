"""Test the closest alternative short-term exposure, PM10, via AERIS tools."""

from __future__ import annotations

import json
from pathlib import Path

from aeris.agent.state import SessionState
from aeris.agentic.contract import execute

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


RUN_DIRECTORY = Path(__file__).resolve().parent
ENV_PATH = Path(".env")
REGIONS = ("Lombardia", "Veneto")
WINDOW = {"start_date": "2020-02-24", "end_date": "2020-05-19"}


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(ENV_PATH, override=False)
    traces, daily_rows = {}, []
    for region in REGIONS:
        state = SessionState()
        state.working_directory = str(RUN_DIRECTORY)
        state.config.openaq_calls_per_minute = 10
        trace = []
        arguments = {
            "pollutant": "pm10",
            "iso3": "ITA",
            "adm_level": 2,
            "boundary_name": region,
            "min_completeness": 75,
            "temporal_resolution": "daily",
            "researcher_approved": True,
            **WINDOW,
        }
        result = execute(state, "estimate_boundary_exposure", arguments)
        trace.append({"tool": "estimate_boundary_exposure", "arguments": arguments, "result": result})
        daily = execute(state, "get_daily_data", {"pollutant": "pm10"})
        trace.append({"tool": "get_daily_data", "arguments": {"pollutant": "pm10"}, "result": daily})
        daily_rows.extend({"region": region, **row} for row in daily.get("data", []))
        traces[region] = trace
    (RUN_DIRECTORY / "aeris_pm10_tool_trace.json").write_text(json.dumps(traces, indent=2) + "\n")
    (RUN_DIRECTORY / "aeris_pm10_daily.json").write_text(json.dumps(daily_rows, indent=2) + "\n")
    print(json.dumps({"daily_rows": len(daily_rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

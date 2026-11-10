"""Fresh post-optimization UK exposure reconstruction through AERIS tools."""

from __future__ import annotations

import json
from pathlib import Path

from aeris.agent.state import SessionState
from aeris.agentic.contract import execute

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - provided by the AERIS environment
    load_dotenv = None


RUN_DIRECTORY = Path(__file__).resolve().parent
_AERIS_ENV = Path(".env")
BOUNDARY_PATH = RUN_DIRECTORY / "boundaries.geojson"
COUNTRIES = ("England", "Scotland", "Wales", "Northern Ireland")
WINDOW = {"start_date": "2020-03-26", "end_date": "2020-09-15"}


def call(trace: list[dict], state: SessionState, name: str, **arguments: object) -> dict:
    result = execute(state, name, arguments)
    trace.append({"tool": name, "arguments": arguments, "result": result})
    return result


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(_AERIS_ENV, override=False)
    traces: dict[str, list[dict]] = {}
    daily_rows: list[dict] = []
    station_rows: list[dict] = []

    for country in COUNTRIES:
        state = SessionState()
        # Leave headroom below OpenAQ's free-tier limit for other study runs.
        state.config.openaq_calls_per_minute = 20
        trace: list[dict] = []
        estimate = call(
            trace,
            state,
            "estimate_boundary_exposure",
            pollutant="pm25",
            boundary_name=country,
            boundary_geojson_path=str(BOUNDARY_PATH),
            min_completeness=75,
            temporal_resolution="daily",
            researcher_approved=True,
            **WINDOW,
        )
        if estimate.get("status") == "ok":
            for row in call(trace, state, "get_daily_data", pollutant="pm25").get("data", []):
                daily_rows.append({"country": country, **row})
            for row in call(trace, state, "get_station_info").get("data", []):
                station_rows.append({"country": country, **row})
        call(trace, state, "get_decision_log")
        traces[country] = trace

    (RUN_DIRECTORY / "aeris_tool_trace.json").write_text(
        json.dumps(traces, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (RUN_DIRECTORY / "aeris_pm25_daily.json").write_text(
        json.dumps(daily_rows, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (RUN_DIRECTORY / "aeris_station_coverage.json").write_text(
        json.dumps(station_rows, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps({"daily_rows": len(daily_rows), "station_rows": len(station_rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

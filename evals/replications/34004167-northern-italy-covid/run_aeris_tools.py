"""Reconstruct Northern Italy daily PM2.5 using only AERIS boundary tools."""

from __future__ import annotations

import json
from pathlib import Path

from aeris.agent.state import SessionState
from aeris.agentic.contract import execute

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - supplied by the AERIS environment
    load_dotenv = None


RUN_DIRECTORY = Path(__file__).resolve().parent
OUTCOME_URL = (
    "https://raw.githubusercontent.com/pcm-dpc/COVID-19/master/"
    "dati-regioni/dpc-covid19-ita-regioni.csv"
)
ENV_PATH = Path(".env")
REGIONS = ("Lombardia", "Veneto")
WINDOW = {"start_date": "2020-02-24", "end_date": "2020-05-19"}


def call(trace: list[dict], state: SessionState, name: str, **arguments: object) -> dict:
    result = execute(state, name, arguments)
    trace.append({"tool": name, "arguments": arguments, "result": result})
    return result


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(ENV_PATH, override=False)

    traces: dict[str, list[dict]] = {}
    daily_rows: list[dict] = []
    station_rows: list[dict] = []

    for region in REGIONS:
        state = SessionState()
        state.working_directory = str(RUN_DIRECTORY)
        state.config.openaq_calls_per_minute = 20
        trace: list[dict] = []
        estimate = call(
            trace,
            state,
            "estimate_boundary_exposure",
            pollutant="pm25",
            iso3="ITA",
            # geoBoundaries represents Italy's 20 administrative regions at ADM2;
            # ADM1 is the five macroregions and cannot represent the study units.
            adm_level=2,
            boundary_name=region,
            min_completeness=75,
            temporal_resolution="daily",
            researcher_approved=True,
            **WINDOW,
        )
        if estimate.get("status") == "ok":
            for row in call(trace, state, "get_daily_data", pollutant="pm25").get("data", []):
                daily_rows.append({"region": region, **row})
            for row in call(trace, state, "get_station_info").get("data", []):
                station_rows.append({"region": region, **row})
        call(trace, state, "get_decision_log")
        traces[region] = trace

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

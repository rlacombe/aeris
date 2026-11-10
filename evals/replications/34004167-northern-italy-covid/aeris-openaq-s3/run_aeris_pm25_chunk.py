"""Run one bounded, resumable AERIS boundary-retrieval slice.

Usage: run_aeris_pm25_chunk.py REGION START_DATE END_DATE
"""

from __future__ import annotations

import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any

from aeris.agent.state import SessionState
from aeris.agentic.contract import execute

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


RUN_DIRECTORY = Path(__file__).resolve().parent
CHUNK_DIRECTORY = RUN_DIRECTORY / "chunks"
CACHE_DIRECTORY = RUN_DIRECTORY / "full-catalog-cache"
ENV_PATH = Path(".env")


def call(trace: list[dict[str, Any]], state: SessionState, name: str, **arguments: object) -> dict:
    result = execute(state, name, arguments)
    trace.append({"tool": name, "arguments": arguments, "result": result})
    return result


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({field for row in rows for field in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        raise SystemExit("Usage: run_aeris_pm25_chunk.py REGION START_DATE END_DATE")
    _, region, start_date, end_date = argv
    logging.disable(logging.WARNING)
    if load_dotenv is not None:
        load_dotenv(ENV_PATH, override=False)
    CHUNK_DIRECTORY.mkdir(exist_ok=True)
    CACHE_DIRECTORY.mkdir(exist_ok=True)

    state = SessionState()
    state.working_directory = str(CACHE_DIRECTORY)
    # Enumerate the complete bounded-box catalogue before polygon containment.
    # A small pre-containment limit can consist entirely of monitors in an
    # adjacent region, yielding a misleading zero-station result.
    state.config.station_limit = 1000
    state.config.openaq_calls_per_minute = 60
    state.config.archive_fallback_max_days = 14
    state.config.archive_fallback_max_objects = 14
    state.config.archive_fallback_enabled = True
    trace: list[dict[str, Any]] = []
    estimate = call(
        trace,
        state,
        "estimate_boundary_exposure",
        pollutant="pm25",
        boundary_geojson_path=str(RUN_DIRECTORY / "geoboundaries_ita_adm2_simplified.geojson"),
        boundary_name=region,
        temporal_resolution="daily",
        min_completeness=0,
        researcher_approved=True,
        start_date=start_date,
        end_date=end_date,
    )
    daily_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    if estimate.get("status") == "ok":
        daily_rows = [{"region": region, **row} for row in call(trace, state, "get_daily_data", pollutant="pm25").get("data", [])]
        station_rows = [{"region": region, **row} for row in call(trace, state, "get_station_info").get("data", [])]
    call(trace, state, "get_decision_log")

    stem = f"{region.lower()}_{start_date}_{end_date}"
    (CHUNK_DIRECTORY / f"{stem}_tool_trace.json").write_text(
        json.dumps(trace, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (CHUNK_DIRECTORY / f"{stem}_summary.json").write_text(
        json.dumps(estimate, indent=2, default=str) + "\n", encoding="utf-8"
    )
    write_csv(CHUNK_DIRECTORY / f"{stem}_daily.csv", daily_rows)
    write_csv(CHUNK_DIRECTORY / f"{stem}_stations.csv", station_rows)
    print(json.dumps({"region": region, "start_date": start_date, "end_date": end_date, "daily_rows": len(daily_rows), "station_rows": len(station_rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

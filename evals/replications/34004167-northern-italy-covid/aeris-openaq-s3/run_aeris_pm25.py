"""Reconstruct the study's regional daily PM2.5 series through public AERIS tools.

This script deliberately uses the public, harness-neutral AERIS contract rather
than direct OpenAQ client calls.  AERIS first requests OpenAQ V3 daily values
and then uses its bounded OpenAQ S3 archive fallback for missing historical
days.  The result is a monitor-weighted regional series: each monitor supplies
one daily mean and the regional value is the unweighted mean of those means.
"""

from __future__ import annotations

import csv
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from aeris.agent.state import SessionState
from aeris.agentic.contract import execute

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - supplied by the AERIS environment
    load_dotenv = None


RUN_DIRECTORY = Path(__file__).resolve().parent
AERIS_DIRECTORY = Path(".")
ENV_PATH = AERIS_DIRECTORY / ".env"
REGIONS = ("Lombardia", "Veneto")
# The official regional Civil Protection series starts 24 February.  This is
# the maximal shared observation window available from that public endpoint.
WINDOW = {"start_date": "2020-02-24", "end_date": "2020-05-19"}


def call(trace: list[dict[str, Any]], state: SessionState, name: str, **arguments: object) -> dict:
    result = execute(state, name, arguments)
    trace.append({"tool": name, "arguments": arguments, "result": result})
    return result


def aeris_revision() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(AERIS_DIRECTORY), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({field for row in rows for field in row})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    # OpenAQ's retry notices are retained in the final tool trace through the
    # returned source records. Suppress streamed warnings so a long, bounded
    # retrieval is not interrupted by the execution host between retries.
    logging.disable(logging.WARNING)
    if load_dotenv is not None:
        load_dotenv(ENV_PATH, override=False)

    trace_by_region: dict[str, list[dict[str, Any]]] = {}
    daily_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for region in REGIONS:
        state = SessionState()
        state.working_directory = str(RUN_DIRECTORY)
        # The target window is 86 days, well inside this explicit archive
        # bound.  The object bound prevents an accidental unbounded download.
        state.config.openaq_calls_per_minute = 20
        state.config.archive_fallback_max_days = 90
        state.config.archive_fallback_max_objects = 90
        state.config.archive_fallback_enabled = True
        trace: list[dict[str, Any]] = []

        estimate = call(
            trace,
            state,
            "estimate_boundary_exposure",
            pollutant="pm25",
            # The exact geoBoundaries download is retained locally as an input
            # so this AERIS call is insulated from transient boundary-host DNS
            # failures. It still selects the named region explicitly.
            boundary_geojson_path=str(RUN_DIRECTORY / "geoboundaries_ita_adm2_simplified.geojson"),
            boundary_name=region,
            temporal_resolution="daily",
            min_completeness=75,
            researcher_approved=True,
            **WINDOW,
        )
        if estimate.get("status") == "ok":
            summary_rows.extend({"region": region, **row} for row in estimate.get("data", []))
            daily_rows.extend(
                {"region": region, **row}
                for row in call(trace, state, "get_daily_data", pollutant="pm25").get("data", [])
            )
            station_rows.extend(
                {"region": region, **row}
                for row in call(trace, state, "get_station_info").get("data", [])
            )
        call(trace, state, "get_decision_log")
        trace_by_region[region] = trace

    provenance = {
        "aeris_revision": aeris_revision(),
        "aeris_contract": "aeris.agentic.contract.execute",
        "pollutant": "pm25",
        "regions": list(REGIONS),
        "window": WINDOW,
        "boundary_input": "geoboundaries_ita_adm2_simplified.geojson",
        "estimand": "unweighted mean of station-day means within the named administrative boundary",
        "retrieval_order": "OpenAQ V3 daily endpoint, then bounded OpenAQ S3 archive fallback",
        "archive_fallback_max_days": 90,
        "archive_fallback_max_objects_per_location": 90,
    }
    (RUN_DIRECTORY / "aeris_tool_trace.json").write_text(
        json.dumps(trace_by_region, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (RUN_DIRECTORY / "aeris_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    write_csv(RUN_DIRECTORY / "aeris_pm25_daily.csv", daily_rows)
    write_csv(RUN_DIRECTORY / "aeris_station_coverage.csv", station_rows)
    write_csv(RUN_DIRECTORY / "aeris_summary.csv", summary_rows)
    print(
        json.dumps(
            {
                "daily_rows": len(daily_rows),
                "station_rows": len(station_rows),
                "summary_rows": len(summary_rows),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

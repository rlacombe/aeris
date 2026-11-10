"""Reconstruct the documented OpenAQ NO2 overlap for PMID 34004167.

The public OpenAQ S3 archive has no PM2.5 rows for the study regions during
the epidemic window. It does expose NO2 beginning on 6 May 2020. This script
uses the same AERIS boundary tool and monitor-weighted estimand for the
two-region, 14-day overlap ending on 19 May 2020.
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
except ImportError:  # pragma: no cover
    load_dotenv = None


RUN_DIRECTORY = Path(__file__).resolve().parent
AERIS_DIRECTORY = Path(".")
ENV_PATH = AERIS_DIRECTORY / ".env"
REGIONS = ("Lombardia", "Veneto")
WINDOW = {"start_date": "2020-05-06", "end_date": "2020-05-19"}


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


def aeris_revision() -> str:
    return subprocess.check_output(
        ["git", "-C", str(AERIS_DIRECTORY), "rev-parse", "HEAD"], text=True
    ).strip()


def main() -> int:
    logging.disable(logging.WARNING)
    if load_dotenv is not None:
        load_dotenv(ENV_PATH, override=False)

    traces: dict[str, list[dict[str, Any]]] = {}
    daily_rows: list[dict[str, Any]] = []
    station_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for region in REGIONS:
        state = SessionState()
        state.working_directory = str(RUN_DIRECTORY / "full-catalog-cache")
        state.config.station_limit = 1000
        state.config.openaq_calls_per_minute = 30
        state.config.archive_fallback_max_days = 14
        state.config.archive_fallback_max_objects = 100
        state.config.archive_fallback_enabled = True
        trace: list[dict[str, Any]] = []
        result = call(
            trace,
            state,
            "estimate_boundary_exposure",
            pollutant="no2",
            boundary_geojson_path=str(RUN_DIRECTORY / "geoboundaries_ita_adm2_simplified.geojson"),
            boundary_name=region,
            temporal_resolution="daily",
            min_completeness=0,
            researcher_approved=True,
            **WINDOW,
        )
        if result.get("status") == "ok":
            summary = result.get("result")
            if isinstance(summary, dict):
                summary_rows.append({"region": region, **summary})
            daily_rows.extend(
                {"region": region, **row}
                for row in call(trace, state, "get_daily_data", pollutant="no2").get("data", [])
            )
            station_rows.extend(
                {"region": region, **row}
                for row in call(trace, state, "get_station_info").get("data", [])
            )
        call(trace, state, "get_decision_log")
        traces[region] = trace

    provenance = {
        "study": "PMID 34004167",
        "aeris_revision": aeris_revision(),
        "aeris_contract": "aeris.agentic.contract.execute",
        "pollutant": "no2",
        "regions": list(REGIONS),
        "window": WINDOW,
        "estimand": "unweighted mean of station-day means within each named administrative boundary",
        "retrieval_order": "OpenAQ V3 daily endpoint, then bounded OpenAQ S3 archive fallback",
    }
    (RUN_DIRECTORY / "aeris_no2_overlap_tool_trace.json").write_text(
        json.dumps(traces, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (RUN_DIRECTORY / "aeris_no2_overlap_provenance.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    write_csv(RUN_DIRECTORY / "aeris_no2_overlap_daily.csv", daily_rows)
    write_csv(RUN_DIRECTORY / "aeris_no2_overlap_stations.csv", station_rows)
    write_csv(RUN_DIRECTORY / "aeris_no2_overlap_summary.csv", summary_rows)
    print(json.dumps({"daily_rows": len(daily_rows), "station_rows": len(station_rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

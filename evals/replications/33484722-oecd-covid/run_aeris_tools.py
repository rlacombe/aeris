"""Reconstruct 2017 OECD-country PM2.5 exposure through the public AERIS contract.

The source study used a World Bank population-weighted annual PM2.5 product.
This run deliberately substitutes AERIS/OpenAQ's documented country-boundary
monitor-network estimand and does not read the authors' exposure values.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from aeris.agent.state import SessionState
from aeris.agentic.contract import execute

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - provided in the AERIS environment
    load_dotenv = None


RUN_DIRECTORY = Path(__file__).resolve().parent
ENV_PATH = Path(".env")
BOUNDARY_PATH = RUN_DIRECTORY / "boundaries" / "natural-earth-v5.1.2-admin0.geojson"

# OECD membership as of March 2020, exactly as listed in PMID 33484722.
COUNTRIES = {
    "AUS": "Australia",
    "AUT": "Austria",
    "BEL": "Belgium",
    "CAN": "Canada",
    "CHL": "Chile",
    "CZE": "Czech Republic",
    "DNK": "Denmark",
    "EST": "Estonia",
    "FIN": "Finland",
    "FRA": "France",
    "DEU": "Germany",
    "GRC": "Greece",
    "HUN": "Hungary",
    "ISL": "Iceland",
    "IRL": "Ireland",
    "ISR": "Israel",
    "ITA": "Italy",
    "JPN": "Japan",
    "KOR": "Republic of Korea",
    "LVA": "Latvia",
    "LTU": "Lithuania",
    "LUX": "Luxembourg",
    "MEX": "Mexico",
    "NLD": "Netherlands",
    "NZL": "New Zealand",
    "NOR": "Norway",
    "POL": "Poland",
    "PRT": "Portugal",
    "SVK": "Slovak Republic",
    "SVN": "Slovenia",
    "ESP": "Spain",
    "SWE": "Sweden",
    "CHE": "Switzerland",
    "TUR": "Turkey",
    "GBR": "United Kingdom",
    "USA": "United States",
}


def call(trace: list[dict], state: SessionState, name: str, **arguments: object) -> dict:
    result = execute(state, name, arguments)
    trace.append({"tool": name, "arguments": arguments, "result": result})
    return result


def read_records(path: Path) -> list[dict]:
    """Load a prior CSV, including the valid empty station-coverage case."""
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        return pd.read_csv(path).to_dict(orient="records")
    except pd.errors.EmptyDataError:
        return []


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(ENV_PATH, override=False)
    # SessionState creates its response cache from the current directory.
    # Keep resumable OpenAQ responses with this study rather than at repo root.
    os.chdir(RUN_DIRECTORY)

    traces: dict[str, list[dict]] = {}
    rows: list[dict] = []
    station_rows: list[dict] = []
    requested = {
        value.strip().upper()
        for value in os.environ.get("AERIS_COUNTRIES", "").split(",")
        if value.strip()
    }
    selected = {iso3: country for iso3, country in COUNTRIES.items() if not requested or iso3 in requested}
    unknown = requested.difference(COUNTRIES)
    if unknown:
        raise ValueError(f"Unknown OECD ISO3 codes: {sorted(unknown)}")

    summary_path = RUN_DIRECTORY / "aeris_pm25_2017_country_summary.csv"
    station_path = RUN_DIRECTORY / "aeris_pm25_2017_station_coverage.csv"
    trace_path = RUN_DIRECTORY / "aeris_tool_trace.json"
    existing_rows = read_records(summary_path)
    existing_stations = read_records(station_path)
    existing_traces = json.loads(trace_path.read_text(encoding="utf-8")) if trace_path.exists() else {}
    existing_rows = [row for row in existing_rows if row.get("iso3") not in selected]
    existing_stations = [row for row in existing_stations if row.get("iso3") not in selected]
    # A bounded location cap keeps this public shared-key run practical while
    # still querying each selected country boundary rather than a centroid.
    # The cap is recorded in every batch manifest and must be reported with
    # the resulting monitor-network estimand.
    station_limit = int(os.environ.get("AERIS_STATION_LIMIT", "50"))
    calls_per_minute = int(os.environ.get("AERIS_CALLS_PER_MINUTE", "10"))
    batch_manifest_path = RUN_DIRECTORY / "aeris_run_manifest.json"
    batch_manifest = {
        "pollutant": "pm25",
        "start_date": "2017-01-01",
        "end_date": "2017-12-31",
        "temporal_resolution": "daily",
        "min_completeness_pct": 75,
        "station_limit": station_limit,
        "openaq_calls_per_minute": calls_per_minute,
        "requested_countries": list(selected),
        "boundary_source": "Natural Earth v5.1.2 Admin 0 GeoJSON",
        "exposure_estimand": "unweighted mean of returned, contributing OpenAQ monitor means within each country boundary",
    }

    for iso3, country in selected.items():
        state = SessionState()
        state.working_directory = str(RUN_DIRECTORY)
        # Use a deliberately conservative shared-key rate.  A persistent run
        # cache makes interrupted country batches resumable without re-querying
        # completed location or sensor-day responses.
        state.config.openaq_calls_per_minute = calls_per_minute
        state.config.station_limit = station_limit
        trace: list[dict] = []
        result = call(
            trace,
            state,
            "estimate_boundary_exposure",
            pollutant="pm25",
            start_date="2017-01-01",
            end_date="2017-12-31",
            boundary_geojson_path=str(BOUNDARY_PATH),
            boundary_name=iso3,
            min_completeness=75,
            temporal_resolution="daily",
            researcher_approved=True,
        )
        if result.get("status") == "ok":
            rows.append({"iso3": iso3, "country": country, **result["result"]})
            station_rows.extend(
                {"iso3": iso3, "country": country, **item}
                for item in call(trace, state, "get_station_info").get("data", [])
            )
        else:
            rows.append({"iso3": iso3, "country": country, "error": result.get("error")})
        call(trace, state, "get_decision_log")
        traces[iso3] = trace

        # Persist each country so an interruption never loses completed API
        # work.  The cache and summary can therefore be resumed country by
        # country with the same settings.
        all_rows = [*existing_rows, *rows]
        all_stations = [*existing_stations, *station_rows]
        all_traces = {**existing_traces, **traces}
        pd.DataFrame(all_rows).to_csv(summary_path, index=False)
        pd.DataFrame(all_stations).to_csv(station_path, index=False)
        trace_path.write_text(
            json.dumps(all_traces, indent=2, default=str) + "\n", encoding="utf-8"
        )
        batch_manifest["completed_countries"] = list(existing_rows and [row.get("iso3") for row in existing_rows] or []) + list(traces)
        batch_manifest["countries_with_valid_estimate"] = [
            row.get("iso3")
            for row in all_rows
            if row.get("mean") is not None and not pd.isna(row.get("mean")) and row.get("qc_flag") == "PASS"
        ]
        batch_manifest_path.write_text(
            json.dumps(batch_manifest, indent=2) + "\n", encoding="utf-8"
        )

    all_rows = [*existing_rows, *rows]
    print(
        json.dumps(
            {
                "countries_completed": len(all_rows),
                "countries_with_data": sum(
                    row.get("mean") is not None and not pd.isna(row.get("mean"))
                    for row in all_rows
                ),
                "station_limit": station_limit,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

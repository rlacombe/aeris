"""Reconstruct PMID 33585383 PM2.5 with resumable annual AERIS tool calls."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

from aeris.agent.state import SessionState
from aeris.agentic.contract import execute
from aeris.exposure.api_clients.openaq_archive import OpenAQArchiveClient
from aeris.exposure.exceptions import UpstreamAPIError
from aeris.exposure.estimators.static import ExposureEstimatorOpenAQStatic

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


RUN_DIRECTORY = Path(__file__).resolve().parent
ENV_PATH = Path(".env")
YEARS = (2014, 2015, 2016)
CHUNK_SIZE = 25
SEARCH_RADIUS_METERS = 100_000
ARCHIVE_LISTING_FAILURES: list[dict[str, str | int]] = []
_LIST_AVAILABLE_DATES = OpenAQArchiveClient.list_available_dates
_NEARBY_STATIONS = ExposureEstimatorOpenAQStatic._nearby_stations


def resilient_list_available_dates(
    client: OpenAQArchiveClient, location_id: int, start_date, end_date
) -> list:
    """Keep direct-v3 exposure rows when a supplementary S3 listing times out."""
    # Historical Chinese location-day objects often take longer than the
    # estimator's default five-second S3 listing timeout.
    client.timeout = (20.0, 60.0)
    errors: list[str] = []
    for attempt in range(1, 4):
        try:
            return _LIST_AVAILABLE_DATES(client, location_id, start_date, end_date)
        except UpstreamAPIError as error:
            errors.append(str(error))
            if attempt < 3:
                time.sleep(attempt)

    ARCHIVE_LISTING_FAILURES.append(
        {
            "location_id": location_id,
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat(),
            "error": errors[-1],
        }
    )
    return []


OpenAQArchiveClient.list_available_dates = resilient_list_available_dates


def catalog_first_nearby_stations(
    estimator: ExposureEstimatorOpenAQStatic, latitude: float, longitude: float
) -> list:
    """Use the loaded national catalog when the public point endpoint caps radius."""
    stations = estimator._catalog_stations(latitude, longitude)
    if stations or estimator._catalog_locations is not None:
        return stations
    return _NEARBY_STATIONS(estimator, latitude, longitude)


ExposureEstimatorOpenAQStatic._nearby_stations = catalog_first_nearby_stations


def call(trace: list[dict], state: SessionState, name: str, **arguments: object) -> dict:
    result = execute(state, name, arguments)
    trace.append({"tool": name, "arguments": arguments, "result": result})
    return result


def build_annual_cohort(year: int, chunk_index: int, outcomes: pd.DataFrame) -> Path:
    cohort = pd.DataFrame(
        {
            "subject_id": outcomes["subject_id"].astype(str),
            "address": outcomes["prefecture"].astype(str).str.strip()
            + ", "
            + outcomes["province"].astype(str).str.strip()
            + ", China",
            "start_date": f"{year}-01-01",
            "end_date": f"{year}-12-31",
        }
    )
    path = RUN_DIRECTORY / "aeris_inputs" / f"cohort_{year}_{chunk_index:02d}.csv"
    path.parent.mkdir(exist_ok=True)
    cohort.to_csv(path, index=False)
    return path


def export_path(year: int, chunk_index: int) -> Path:
    return RUN_DIRECTORY / f"aeris_pm25_{year}_{chunk_index:02d}.csv"


def write_run_record(trace: list[dict]) -> None:
    run_record = {
        "tool_trace": trace,
        "archive_listing_failures": ARCHIVE_LISTING_FAILURES,
        "search_radius_meters": SEARCH_RADIUS_METERS,
        "openaq_calls_per_minute": 60,
    }
    (RUN_DIRECTORY / "aeris_annual_tool_trace.json").write_text(
        json.dumps(run_record, indent=2, default=str) + "\n", encoding="utf-8"
    )


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(ENV_PATH, override=False)

    outcomes = pd.read_csv(RUN_DIRECTORY / "public_inputs" / "outcomes_without_author_exposure.csv")
    trace: list[dict] = []
    for year in YEARS:
        annual_paths: list[Path] = []
        for chunk_index, start in enumerate(range(0, len(outcomes), CHUNK_SIZE), start=1):
            output = export_path(year, chunk_index)
            if output.exists():
                annual_paths.append(output)
                continue

            cohort = build_annual_cohort(
                year, chunk_index, outcomes.iloc[start : start + CHUNK_SIZE].copy()
            )
            state = SessionState()
            state.config.openaq_calls_per_minute = 60
            state.config.search_radius = SEARCH_RADIUS_METERS
            state.config.archive_fallback_max_days = 400
            call(trace, state, "load_cohort", path=str(cohort))
            call(
                trace,
                state,
                "plan_exposure",
                pollutant="pm25",
                country="cn",
                temporal_resolution="daily",
                location_strategy="auto",
                n_stations=1,
            )
            estimate = call(
                trace,
                state,
                "estimate_exposure",
                pollutant="pm25",
                country="cn",
                n_stations=1,
                min_completeness=None,
                temporal_resolution="daily",
                location_strategy="auto",
                researcher_approved=True,
            )
            trace[-1]["year"] = year
            trace[-1]["chunk_index"] = chunk_index
            if estimate.get("status") == "ok" and estimate.get("n_results", 0):
                call(trace, state, "export_results", path=str(output))
                annual_paths.append(output)
                call(trace, state, "get_exposure_summary", pollutant="pm25")
            call(trace, state, "get_decision_log")
            write_run_record(trace)

        if annual_paths:
            annual = pd.concat((pd.read_csv(path) for path in annual_paths), ignore_index=True)
            annual.to_csv(RUN_DIRECTORY / f"aeris_pm25_{year}.csv", index=False)
            write_run_record(trace)

    write_run_record(trace)
    run_record = json.loads((RUN_DIRECTORY / "aeris_annual_tool_trace.json").read_text())
    print(json.dumps(run_record, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Reconstruct 2019 department PM2.5 records through AERIS/OpenAQ.

The runner checkpoints after every department. Re-run it after an interruption;
completed department records are retained and not requested again.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

import pandas as pd
from shapely.geometry import shape

from aeris.exposure.boundaries import AdministrativeBoundary
from aeris.exposure.cache import ResponseCache
from aeris.exposure.config import Config
from aeris.exposure.estimators.boundary import ExposureEstimatorOpenAQBoundary

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "aeris_pm25_2019.csv"
FAILURES = ROOT / "aeris_pm25_2019_failures.jsonl"


def normalized_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return "".join(character for character in value.casefold() if character.isalnum())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Run at most this many pending departments.")
    parser.add_argument("--department", action="append", help="Run one named department; repeat as needed.")
    parser.add_argument("--pause-seconds", type=float, default=8.0)
    parser.add_argument(
        "--v3-only",
        action="store_true",
        help="Use OpenAQ v3 daily records only; retain coverage failures for the audit.",
    )
    parser.add_argument(
        "--department-timeout-seconds",
        type=float,
        default=180.0,
        help="Process-level deadline for one department; timed-out departments are recorded and skipped.",
    )
    parser.add_argument("--child", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    panel = pd.read_csv(ROOT / "analysis_panel_pre_exposure.csv")
    wanted = set(panel["department_name"])
    if args.department:
        wanted = set(args.department)

    existing = pd.read_csv(OUTPUT) if OUTPUT.exists() else pd.DataFrame()
    completed = set(existing["boundary_name"]) if not existing.empty else set()
    geojson = json.loads((ROOT / "france_departments.geojson").read_text())
    geometry_by_key = {
        normalized_name(feature["properties"]["shapeName"]): feature for feature in geojson["features"]
    }
    wanted_by_key = {normalized_name(name): name for name in wanted}
    missing_geometries = set(wanted_by_key) - set(geometry_by_key)
    if missing_geometries:
        raise ValueError(f"No geoBoundaries geometry for: {sorted(missing_geometries)}")

    cache = ResponseCache(ROOT / ".aeris_openaq_cache.sqlite")
    config = Config.from_env()
    # Conservative client-level pacing. The pause below also protects the shared
    # API key between separate department estimators.
    config.openaq_calls_per_minute = 12
    config.openaq_calls_per_hour = 500
    config.archive_fallback_enabled = not args.v3_only
    pending = [name for name in sorted(wanted) if name not in completed]
    if args.limit is not None:
        pending = pending[: args.limit]

    if not args.child:
        for index, name in enumerate(pending, start=1):
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--department",
                name,
                "--child",
                "--pause-seconds",
                "0",
                "--department-timeout-seconds",
                str(args.department_timeout_seconds),
            ]
            if args.v3_only:
                command.append("--v3-only")
            try:
                subprocess.run(command, check=True, timeout=args.department_timeout_seconds)
            except subprocess.TimeoutExpired:
                failure = {"department_name": name, "status": "timeout"}
                with FAILURES.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(failure) + "\n")
                print(f"{index}/{len(pending)} {name}: TIMEOUT")
            except subprocess.CalledProcessError as exc:
                failure = {"department_name": name, "status": "error", "returncode": exc.returncode}
                with FAILURES.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(failure) + "\n")
                print(f"{index}/{len(pending)} {name}: ERROR")
            if index < len(pending):
                time.sleep(args.pause_seconds)
        return

    for index, name in enumerate(pending, start=1):
        feature = geometry_by_key[normalized_name(name)]
        boundary = AdministrativeBoundary(
            name=name,
            geometry=shape(feature["geometry"]),
            source="geoBoundaries_gbOpen",
            metadata={
                "boundary_id": "FRA-ADM2-29444166",
                "geoBoundaries_release_commit": "9469f09",
                "properties": feature["properties"],
            },
        )
        estimator = ExposureEstimatorOpenAQBoundary(
            boundary=boundary,
            start_date="2019-01-01",
            end_date="2019-12-31",
            pollutant="pm25",
            temporal_resolution="daily",
            cache=cache,
            config=config,
        )
        record = estimator.run().iloc[0].to_dict()
        updated = pd.concat([existing, pd.DataFrame([record])], ignore_index=True)
        updated.to_csv(OUTPUT, index=False)
        existing = updated
        print(
            f"{index}/{len(pending)} {name}: {record['qc_flag']} "
            f"stations={record['n_stations']} coverage={record['network_temporal_coverage_pct']:.1f}%"
        )
        if index < len(pending):
            time.sleep(args.pause_seconds)


if __name__ == "__main__":
    main()

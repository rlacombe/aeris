#!/usr/bin/env python3
"""Run the public AERIS tool contract for a Sao Paulo municipal PM2.5 record."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"


def load_dotenv(path: Path) -> None:
    """Load only unset variables; credentials remain in the AERIS checkout."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aeris-repo", type=Path, default=Path(os.environ.get("AERIS_REPO", ".")))
    parser.add_argument("--start-date", default="2019-01-01")
    parser.add_argument("--end-date", default="2019-12-31")
    parser.add_argument("--min-completeness", type=float, default=50.0)
    args = parser.parse_args()

    if not (args.aeris_repo / "aeris").exists():
        raise FileNotFoundError(f"AERIS checkout not found: {args.aeris_repo}")
    boundary = RAW / "sao_paulo_3550308.geojson"
    if not boundary.exists():
        raise FileNotFoundError(f"Boundary not found: {boundary}. Run fetch_boundary.py first.")
    load_dotenv(args.aeris_repo / ".env")
    sys.path.insert(0, str(args.aeris_repo))
    os.chdir(ROOT)

    from aeris.agent.state import SessionState
    from aeris.agentic.contract import execute

    DERIVED.mkdir(parents=True, exist_ok=True)
    state = SessionState()
    dag_result = execute(
        state,
        "record_dag",
        {
            "research_question": "What is the association between short-term municipal PM2.5 and daily cancer mortality in Sao Paulo in 2019?",
            "nodes": [
                {"name": "PM2.5", "role": "exposure", "description": "AERIS monitor-network daily municipal PM2.5."},
                {"name": "Cancer mortality", "role": "outcome", "description": "Daily SIM cancer deaths."},
                {"name": "Weather", "role": "confounder", "description": "Daily temperature and relative humidity."},
                {"name": "Calendar", "role": "confounder", "description": "Weekday, month, and holiday timing."},
            ],
            "edges": [
                {"source": "Weather", "target": "PM2.5"},
                {"source": "Weather", "target": "Cancer mortality"},
                {"source": "Calendar", "target": "PM2.5"},
                {"source": "Calendar", "target": "Cancer mortality"},
                {"source": "PM2.5", "target": "Cancer mortality"},
            ],
            "reasoning": "The calendar matching controls month and weekday by design. Weather remains a time-varying adjustment variable.",
            "adjustment_recommendation": "Adjust for temperature, relative humidity, and public holidays; researcher review required.",
        },
    )
    result = execute(
        state,
        "estimate_boundary_exposure",
        {
            "pollutant": "pm25",
            "start_date": args.start_date,
            "end_date": args.end_date,
            "boundary_geojson_path": str(boundary),
            "min_completeness": args.min_completeness,
            "temporal_resolution": "daily",
            "researcher_approved": True,
        },
    )
    candidate_stations = state.estimator.discover_stations() if state.estimator is not None else []
    daily = state.estimator.get_daily_data() if state.estimator is not None else None
    stations = state.estimator.get_station_info() if state.estimator is not None else None
    if daily is not None:
        daily.to_csv(DERIVED / "aeris_pm25_daily.csv", index=False)
    if stations is not None:
        stations.to_csv(DERIVED / "aeris_pm25_stations.csv", index=False)
    (DERIVED / "aeris_pm25_candidate_stations.json").write_text(
        json.dumps(candidate_stations, indent=2, default=str) + "\n"
    )
    record = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "aeris_repo": str(args.aeris_repo),
        "tool": "estimate_boundary_exposure",
        "arguments": {
            "pollutant": "pm25",
            "start_date": args.start_date,
            "end_date": args.end_date,
            "boundary_geojson_path": str(boundary),
            "min_completeness": args.min_completeness,
            "temporal_resolution": "daily",
        },
        "dag_result": dag_result,
        "tool_result": result,
        "daily_rows": 0 if daily is None else len(daily),
        "station_rows": 0 if stations is None else len(stations),
        "candidate_stations": candidate_stations,
    }
    (DERIVED / "aeris_exposure_run.json").write_text(json.dumps(record, indent=2, default=str) + "\n")
    print(json.dumps(record, indent=2, default=str))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())

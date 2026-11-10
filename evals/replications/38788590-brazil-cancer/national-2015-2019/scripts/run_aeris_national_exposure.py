#!/usr/bin/env python3
"""Construct a 2015--2019 national monitor-network PM2.5 record with AERIS."""
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
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aeris-repo", type=Path, default=Path(os.environ.get("AERIS_REPO", ".")))
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2019)
    parser.add_argument("--min-completeness", type=float, default=0.0)
    args = parser.parse_args()
    if not (args.aeris_repo / "aeris").is_dir():
        raise FileNotFoundError(f"AERIS checkout not found: {args.aeris_repo}")
    boundary = RAW / "brazil_adm0.geojson"
    if not boundary.exists():
        raise FileNotFoundError("Run fetch_boundary.py first.")
    load_dotenv(args.aeris_repo / ".env")
    sys.path.insert(0, str(args.aeris_repo))
    os.chdir(ROOT)
    from aeris.agent.state import SessionState
    from aeris.agentic.contract import execute

    state = SessionState()
    dag = execute(state, "record_dag", {
        "research_question": "What is the association between short-term nationwide monitor-network PM2.5 and daily cancer mortality in Brazil, 2015--2019?",
        "nodes": [
            {"name": "PM2.5", "role": "exposure", "description": "AERIS national monitor-network daily PM2.5."},
            {"name": "Cancer mortality", "role": "outcome", "description": "Daily national SIM cancer deaths."},
            {"name": "Weather", "role": "confounder", "description": "Network-location daily temperature and humidity."},
            {"name": "Calendar", "role": "confounder", "description": "Weekday, month, and national holiday."},
        ],
        "edges": [
            {"source": "Weather", "target": "PM2.5"}, {"source": "Weather", "target": "Cancer mortality"},
            {"source": "Calendar", "target": "PM2.5"}, {"source": "Calendar", "target": "Cancer mortality"},
            {"source": "PM2.5", "target": "Cancer mortality"},
        ],
        "reasoning": "Case-crossover strata control month and weekday. Weather remains a time-varying adjustment.",
        "adjustment_recommendation": "Adjust for daily temperature, relative humidity, and national holiday; researcher review required.",
    })
    DERIVED.mkdir(parents=True, exist_ok=True)
    # AERIS deliberately bounds a single archive request to 400 days. One
    # approved request per calendar year preserves that guardrail while
    # reconstructing the paper's full five-year window.
    results, daily_frames, station_frames = [], [], []
    for year in range(args.start_year, args.end_year + 1):
        year_state = SessionState()
        arguments = {
            "pollutant": "pm25", "start_date": f"{year}-01-01", "end_date": f"{year}-12-31",
            "boundary_geojson_path": str(boundary), "min_completeness": args.min_completeness,
            "temporal_resolution": "daily", "researcher_approved": True,
        }
        result = execute(year_state, "estimate_boundary_exposure", arguments)
        daily = year_state.estimator.get_daily_data() if year_state.estimator is not None else None
        stations = year_state.estimator.get_station_info() if year_state.estimator is not None else None
        if daily is not None and not daily.empty:
            daily_frames.append(daily)
        if stations is not None and not stations.empty:
            station_frames.append(stations)
        results.append({"year": year, "arguments": arguments, "result": result,
                        "daily_rows": 0 if daily is None else len(daily),
                        "station_rows": 0 if stations is None else len(stations)})
    daily = None if not daily_frames else __import__("pandas").concat(daily_frames, ignore_index=True).drop_duplicates()
    stations = None if not station_frames else __import__("pandas").concat(station_frames, ignore_index=True).drop_duplicates()
    if daily is not None:
        daily.to_csv(DERIVED / "aeris_national_pm25_daily.csv", index=False)
    if stations is not None:
        stations.to_csv(DERIVED / "aeris_national_pm25_stations.csv", index=False)
    record = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "aeris_repo": str(args.aeris_repo),
        "tool": "estimate_boundary_exposure", "strategy": "One bounded AERIS request per calendar year.",
        "dag_result": dag, "yearly_runs": results,
        "daily_rows": 0 if daily is None else len(daily), "station_rows": 0 if stations is None else len(stations),
    }
    (DERIVED / "aeris_national_tool_trace.json").write_text(json.dumps(record, indent=2, default=str) + "\n")
    print(json.dumps(record, indent=2, default=str))
    return 0 if all(run["result"].get("status") == "ok" for run in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

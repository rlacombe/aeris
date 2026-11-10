#!/usr/bin/env python3
"""Request the study-period daily boundary exposures through the AERIS tool contract."""

from __future__ import annotations

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
            os.environ.setdefault(key.strip(), value.strip().strip("\"'") )


def main() -> int:
    aeris_repo = Path(os.environ.get("AERIS_REPO", "."))
    if not (aeris_repo / "aeris").exists():
        raise FileNotFoundError(f"AERIS checkout not found: {aeris_repo}")
    boundary = RAW / "sao_paulo_metropolitan_39.geojson"
    if not boundary.exists():
        raise FileNotFoundError("Run fetch_boundary.py first.")
    load_dotenv(aeris_repo / ".env")
    sys.path.insert(0, str(aeris_repo))
    os.chdir(ROOT)
    from aeris.agent.state import SessionState
    from aeris.agentic.contract import execute

    DERIVED.mkdir(parents=True, exist_ok=True)
    records = []
    for pollutant in ("pm25", "pm10", "no2"):
        state = SessionState()
        dag = execute(state, "record_dag", {
            "research_question": "How did daily environmental conditions relate to acute myocardial-infarction admissions in metropolitan Sao Paulo from 2012 through 2015?",
            "nodes": [
                {"name": pollutant.upper(), "role": "exposure", "description": "AERIS daily ambient boundary exposure."},
                {"name": "MI admissions", "role": "outcome", "description": "Public daily SIH/SUS I21 admissions."},
                {"name": "Weather", "role": "confounder", "description": "Daily temperature, humidity, and rainfall."},
                {"name": "Calendar", "role": "confounder", "description": "Season and day-of-week timing."},
            ],
            "edges": [{"source": "Weather", "target": pollutant.upper()}, {"source": "Weather", "target": "MI admissions"}, {"source": "Calendar", "target": pollutant.upper()}, {"source": "Calendar", "target": "MI admissions"}, {"source": pollutant.upper(), "target": "MI admissions"}],
            "reasoning": "The reconstruction follows the paper's multivariable daily environmental-cluster design.",
            "adjustment_recommendation": "Review weather and calendar adjustment before interpreting any association."
        })
        result = execute(state, "estimate_boundary_exposure", {
            "pollutant": pollutant,
            "start_date": "2012-01-01",
            "end_date": "2015-12-31",
            "boundary_geojson_path": str(boundary),
            "min_completeness": 0,
            "temporal_resolution": "daily",
            "researcher_approved": True,
        })
        daily = state.estimator.get_daily_data() if state.estimator is not None else None
        stations = state.estimator.get_station_info() if state.estimator is not None else None
        if daily is not None:
            daily.to_csv(DERIVED / f"aeris_{pollutant}_daily.csv", index=False)
        if stations is not None:
            stations.to_csv(DERIVED / f"aeris_{pollutant}_stations.csv", index=False)
        records.append({"pollutant": pollutant, "dag": dag, "result": result, "daily_rows": 0 if daily is None else len(daily), "station_rows": 0 if stations is None else len(stations)})
    trace = {"run_at_utc": datetime.now(timezone.utc).isoformat(), "aeris_repo": str(aeris_repo), "boundary": str(boundary), "records": records}
    (DERIVED / "aeris_tool_trace.json").write_text(json.dumps(trace, indent=2, default=str) + "\n")
    print(json.dumps(trace, indent=2, default=str))
    return 0 if all(record["result"].get("status") == "ok" for record in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())

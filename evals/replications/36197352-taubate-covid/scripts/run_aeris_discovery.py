#!/usr/bin/env python3
"""Run AERIS monitor discovery for the Taubate conurbation."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
AERIS_REPO = Path(os.environ.get("AERIS_REPO", "."))


def main() -> int:
    sys.path.insert(0, str(AERIS_REPO))
    from aeris.agent import tools
    from aeris.agent.state import SessionState

    DERIVED.mkdir(parents=True, exist_ok=True)
    cohort = pd.DataFrame(
        {
            "subject_id": ["taubate", "tremembe", "pindamonhangaba"],
            "address": [
                "Taubate, Sao Paulo, Brazil",
                "Tremembe, Sao Paulo, Brazil",
                "Pindamonhangaba, Sao Paulo, Brazil",
            ],
            "start_date": ["2020-04-01"] * 3,
            "end_date": ["2021-03-31"] * 3,
        }
    )
    cohort_path = DERIVED / "aeris_cohort.csv"
    cohort.to_csv(cohort_path, index=False)
    state = SessionState()
    trace: list[dict] = []

    def call(name: str, **kwargs):
        result = getattr(tools, name)(state=state, **kwargs)
        trace.append({"tool": name, "arguments": kwargs, "result": result})
        return result

    call("open_folder", path=str(ROOT))
    call("load_cohort", path=str(cohort_path))
    results = {}
    for pollutant in ("pm25", "no2", "o3"):
        results[pollutant] = call(
            "estimate_exposure",
            pollutant=pollutant,
            country="br",
            n_stations=20,
            outlier_detection=False,
            researcher_approved=True,
        )
        if results[pollutant].get("status") == "ok":
            for subject in cohort["subject_id"]:
                call("get_daily_data", subject_id=subject, pollutant=pollutant)
    station_info = call("get_station_info")
    decision_log = call("get_decision_log")
    record = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "aeris_repo": str(AERIS_REPO),
        "cohort": cohort.to_dict(orient="records"),
        "results": results,
        "station_info": station_info,
        "decision_log": decision_log,
    }
    (DERIVED / "aeris_tool_trace.json").write_text(json.dumps(trace, indent=2, default=str) + "\n")
    (DERIVED / "aeris_discovery.json").write_text(json.dumps(record, indent=2, default=str) + "\n")
    print(json.dumps(record, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

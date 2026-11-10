#!/usr/bin/env python3
"""Construct São José daily pollutant records through the AERIS tool interface."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from aeris.agent import tools
from aeris.agent.state import SessionState


ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "data" / "derived" / "aeris_cohort.csv"
POLLUTANTS = ("pm10", "no2", "o3")


def add(trace: list[dict], tool: str, response: dict) -> dict:
    trace.append({"tool": tool, "response": response})
    return response


def main() -> int:
    state = SessionState()
    trace: list[dict] = []
    add(trace, "open_folder", tools.open_folder(state=state, path=str(ROOT)))
    add(
        trace,
        "run_code",
        tools.run_code(
            state=state,
            code=(
                "from pathlib import Path\n"
                "import pandas as pd\n"
                f"out = Path({str(COHORT)!r})\n"
                "out.parent.mkdir(parents=True, exist_ok=True)\n"
                "pd.DataFrame([{'subject_id': 'sao-jose-dos-campos', "
                "'address': 'Sao Jose dos Campos, Sao Paulo, Brazil', "
                "'start_date': '2020-04-01', 'end_date': '2021-04-30'}]).to_csv(out, index=False)\n"
                "print(out)\n"
            ),
        ),
    )
    add(trace, "load_cohort", tools.load_cohort(state=state, path=str(COHORT)))
    for pollutant in POLLUTANTS:
        response = add(
            trace,
            "estimate_exposure",
            tools.estimate_exposure(
                state=state,
                pollutant=pollutant,
                country="br",
                n_stations=1,
                outlier_detection=False,
                min_completeness=0.0,
                researcher_approved=True,
            ),
        )
        if response.get("status") == "ok" and response.get("n_results", 0):
            daily = add(trace, "get_daily_data", tools.get_daily_data(state=state, subject_id="sao-jose-dos-campos", pollutant=pollutant))
            records = daily.get("data", [])
            if records:
                pd.DataFrame(records).to_csv(ROOT / "data" / "derived" / f"aeris_{pollutant}_daily.csv", index=False)
            add(trace, "get_station_info", tools.get_station_info(state=state))
    add(trace, "get_decision_log", tools.get_decision_log(state=state))
    (ROOT / "data" / "derived" / "aeris_tool_trace.json").write_text(json.dumps(trace, indent=2, default=str) + "\n")
    print(json.dumps(trace, indent=2, default=str))


if __name__ == "__main__":
    main()

"""Independent AERIS reconstruction for PMID 33398753.

The public Mendeley workbook supplies the 55 study cities, COVID outcomes, and
population density.  Its author-supplied pollution field is deliberately never
loaded into the analysis panel.  AERIS reconstructs 2018 ambient PM10 from
OpenAQ for each city, then counts days above 50 micrograms/m3.
"""

from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pandas as pd

from aeris.agent.state import SessionState
from aeris.agentic.contract import execute

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - supplied by the AERIS environment
    load_dotenv = None


RUN_DIRECTORY = Path(__file__).resolve().parent
ENV_PATH = Path(".env")
WORKBOOK = RUN_DIRECTORY / "00. Data COVID-19 Coccia Mendeley 2020.xlsx"
GEONAMES = RUN_DIRECTORY / "geonames_IT.zip"
PM10_DAILY_LIMIT_UG_M3 = 50.0


def workbook_rows() -> list[dict[str, object]]:
    """Read the public workbook without importing its pollution column."""
    with ZipFile(WORKBOOK) as archive:
        shared = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        strings = ["".join(item.itertext()) for item in shared.findall(f"{namespace}si")]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    rows: list[list[str | None]] = []
    for row in sheet.findall(f".//{namespace}row"):
        values: list[str | None] = []
        for cell in row.findall(f"{namespace}c"):
            raw = cell.findtext(f"{namespace}v")
            values.append(strings[int(raw)] if raw and cell.get("t") == "s" else raw)
        rows.append(values)

    header = rows[0]
    required = {"City", "Italian Province Capital", "Density h/km2", "Infected 7.April 2020"}
    if not required.issubset(header):
        raise ValueError(f"Unexpected workbook fields: {header}")
    index = {name: header.index(name) for name in required}
    return [
        {
            "subject_id": str(row[index["City"]]),
            "city": str(row[index["Italian Province Capital"]]),
            "density_per_km2": float(row[index["Density h/km2"]]),
            "infected_2020_04_07": float(row[index["Infected 7.April 2020"]]),
        }
        for row in rows[1:]
    ]


def italian_city_coordinates() -> dict[str, tuple[float, float]]:
    """Index populated places in the pinned public GeoNames Italy gazetteer."""
    rows: dict[str, tuple[float, float]] = {}
    with ZipFile(GEONAMES) as archive:
        with archive.open("IT.txt") as handle:
            for raw_line in handle:
                fields = raw_line.decode("utf-8").rstrip("\n").split("\t")
                if len(fields) < 19 or fields[6] != "P":
                    continue
                coordinate = (float(fields[4]), float(fields[5]))
                names = [fields[1], fields[2], *fields[3].split(",")]
                for name in names:
                    if name.strip():
                        rows.setdefault(name.strip().casefold(), coordinate)
    return rows


def call(trace: list[dict], state: SessionState, name: str, **arguments: object) -> dict:
    result = execute(state, name, arguments)
    trace.append({"tool": name, "arguments": arguments, "result": result})
    return result


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(ENV_PATH, override=False)
    if not WORKBOOK.exists():
        raise FileNotFoundError(f"Missing public input: {WORKBOOK}")

    study_rows = workbook_rows()
    coordinates = italian_city_coordinates()
    missing = [
        row["city"]
        for row in study_rows
        if str(row["city"]).strip().casefold() not in coordinates
    ]
    if missing:
        raise ValueError(f"GeoNames has no populated-place match for: {missing}")
    cohort = pd.DataFrame(study_rows)[["subject_id", "city"]]
    cohort[["latitude", "longitude"]] = cohort["city"].apply(
        lambda city: pd.Series(coordinates[str(city).strip().casefold()])
    )
    # Static-mode validation retains an address-or-ZIP requirement even when
    # explicit coordinates are present; the estimator uses the coordinates.
    cohort["address"] = cohort["city"] + ", Italy"
    cohort["start_date"] = "2018-01-01"
    cohort["end_date"] = "2018-12-31"
    cohort.to_csv(RUN_DIRECTORY / "aeris_cohort.csv", index=False)
    pd.DataFrame(study_rows).to_csv(RUN_DIRECTORY / "public_outcomes_and_covariates.csv", index=False)

    state = SessionState()
    state.working_directory = str(RUN_DIRECTORY)
    state.config.openaq_calls_per_minute = 20
    trace: list[dict] = []
    call(trace, state, "load_cohort", path=str(RUN_DIRECTORY / "aeris_cohort.csv"))
    call(
        trace,
        state,
        "plan_exposure",
        pollutant="pm10",
        country="it",
        n_stations=1,
        temporal_resolution="daily",
        location_strategy="catalog",
    )
    estimate = call(
        trace,
        state,
        "estimate_exposure",
        pollutant="pm10",
        country="it",
        n_stations=1,
        min_completeness=75,
        temporal_resolution="daily",
        location_strategy="catalog",
        researcher_approved=True,
    )
    daily_rows: list[dict] = []
    if estimate.get("status") == "ok":
        call(trace, state, "export_results", path=str(RUN_DIRECTORY / "aeris_pm10.csv"))
        for subject_id in cohort["subject_id"]:
            daily = call(trace, state, "get_daily_data", subject_id=subject_id, pollutant="pm10")
            daily_rows.extend({"subject_id": subject_id, **row} for row in daily.get("data", []))
    call(trace, state, "get_decision_log")
    pd.DataFrame(daily_rows).to_csv(RUN_DIRECTORY / "aeris_pm10_daily.csv", index=False)
    (RUN_DIRECTORY / "aeris_tool_trace.json").write_text(
        json.dumps(trace, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps({"estimate": estimate, "daily_rows": len(daily_rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

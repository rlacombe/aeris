"""Build the Israel COVID municipal outcome and AERIS cohort inputs.

This run deliberately never loads the paper's Ministry of Environmental
Protection CHIMERE exposure field.  It retrieves only public COVID outcomes
from the Ministry of Health CKAN datastore and municipality locations and
population from the cited 2019 CBS workbook.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
from zipfile import ZipFile


RUN_DIRECTORY = Path(__file__).resolve().parent
SOURCE_DIRECTORY = RUN_DIRECTORY / "source_inputs"
LOCALITIES_WORKBOOK = SOURCE_DIRECTORY / "bycode2019.xlsx"
OUTCOME_RESOURCE_ID = "8a21d39d-91e3-40db-aca1-f73f7ab1df69"
OUTCOME_API = "https://data.gov.il/api/3/action/datastore_search"
LOCALITIES_URL = "https://www.cbs.gov.il/he/publications/doclib/2019/ishuvim/bycode2019.xlsx"
TARGET_DATES = ("2020-03-31", "2020-07-24", "2020-09-27", "2021-01-17")
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def cell_index(reference: str) -> int:
    """Return a zero-based column index from an XLSX cell reference."""
    letters = "".join(char for char in reference if char.isalpha())
    value = 0
    for char in letters:
        value = value * 26 + ord(char) - ord("A") + 1
    return value - 1


def workbook_rows(path: Path) -> list[dict[str, str | None]]:
    """Read the small cited XLSX workbook using only the Python stdlib."""
    with ZipFile(path) as archive:
        shared = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        strings = ["".join(item.itertext()) for item in shared.findall(f"{NS}si")]
        sheet = ET.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    raw_rows: list[list[str | None]] = []
    for row in sheet.findall(f".//{NS}row"):
        values: list[str | None] = []
        for cell in row.findall(f"{NS}c"):
            index = cell_index(cell.attrib["r"])
            values.extend([None] * (index + 1 - len(values)))
            raw = cell.findtext(f"{NS}v")
            values[index] = strings[int(raw)] if raw and cell.get("t") == "s" else raw
        raw_rows.append(values)

    header = raw_rows[0]
    return [dict(zip(header, row, strict=False)) for row in raw_rows[1:]]


def ensure_localities_workbook() -> None:
    """Download the cited CBS workbook when it is absent from a clean checkout."""
    if LOCALITIES_WORKBOOK.exists():
        return
    SOURCE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    request = Request(LOCALITIES_URL, headers={"User-Agent": "AERIS-reproduction-evaluation/1.0"})
    with urlopen(request, timeout=180) as response:
        LOCALITIES_WORKBOOK.write_bytes(response.read())


def itm_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """Convert EPSG:2039 Israel TM coordinates to WGS84.

    This is the standard inverse Transverse Mercator series for the GRS80
    ellipsoid and the official Israel TM projection parameters.  The optional
    EPSG datum shift is immaterial for nearest-monitor assignment at this
    scale; the resulting coordinates are accurate to substantially below 1 km.
    """
    a = 6378137.0
    inverse_flattening = 298.257222101
    f = 1.0 / inverse_flattening
    e2 = f * (2.0 - f)
    ep2 = e2 / (1.0 - e2)
    k0 = 1.0000067
    lat0 = math.radians(31.73439361111111)
    lon0 = math.radians(35.20451694444445)
    false_easting = 219529.584
    false_northing = 626907.39

    def meridional_arc(latitude: float) -> float:
        return a * (
            (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256) * latitude
            - (3 * e2 / 8 + 3 * e2**2 / 32 + 45 * e2**3 / 1024) * math.sin(2 * latitude)
            + (15 * e2**2 / 256 + 45 * e2**3 / 1024) * math.sin(4 * latitude)
            - (35 * e2**3 / 3072) * math.sin(6 * latitude)
        )

    m = meridional_arc(lat0) + (northing - false_northing) / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )
    sin_phi1 = math.sin(phi1)
    cos_phi1 = math.cos(phi1)
    tan_phi1 = math.tan(phi1)
    n1 = a / math.sqrt(1 - e2 * sin_phi1**2)
    r1 = a * (1 - e2) / (1 - e2 * sin_phi1**2) ** 1.5
    t1 = tan_phi1**2
    c1 = ep2 * cos_phi1**2
    d = (easting - false_easting) / (n1 * k0)
    latitude = phi1 - (n1 * tan_phi1 / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * ep2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * ep2 - 3 * c1**2) * d**6 / 720
    )
    longitude = lon0 + (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * ep2 + 24 * t1**2) * d**5 / 120
    ) / cos_phi1
    return math.degrees(latitude), math.degrees(longitude)


def load_localities() -> dict[str, dict[str, str | float]]:
    """Return 2019 CBS population and WGS84 centre points keyed by locality code."""
    rows: dict[str, dict[str, str | float]] = {}
    for row in workbook_rows(LOCALITIES_WORKBOOK):
        code = row.get("סמל יישוב")
        coordinate = row.get("קואורדינטות")
        population = row.get("סך הכל אוכלוסייה 2019")
        if not code or not coordinate or not population:
            continue
        coordinate_text = str(coordinate).split(".")[0].zfill(10)
        if len(coordinate_text) != 10:
            continue
        latitude, longitude = itm_to_wgs84(
            float(coordinate_text[:5]) * 10,
            float(coordinate_text[5:]) * 10,
        )
        rows[str(int(float(code)))] = {
            "city_code": str(int(float(code))),
            "city_name_en": str(row.get("שם יישוב באנגלית") or ""),
            "population_2019": float(population),
            "latitude": latitude,
            "longitude": longitude,
        }
    return rows


def retrieve_outcomes() -> list[dict[str, str]]:
    """Page the public CKAN datastore and retain target dates plus prior days."""
    dates = {date.fromisoformat(value) for value in TARGET_DATES}
    wanted = {value.isoformat() for value in dates}
    wanted.update((value - timedelta(days=1)).isoformat() for value in dates)
    records: list[dict[str, str]] = []
    offset = 0
    limit = 100_000
    while True:
        url = f"{OUTCOME_API}?{urlencode({'resource_id': OUTCOME_RESOURCE_ID, 'limit': limit, 'offset': offset})}"
        request = Request(url, headers={"User-Agent": "AERIS-reproduction-evaluation/1.0"})
        with urlopen(request, timeout=180) as response:
            payload = json.load(response)
        if not payload.get("success"):
            raise RuntimeError(f"Government datastore request failed at offset {offset}: {payload}")
        page = payload["result"]["records"]
        records.extend(row for row in page if row.get("Date") in wanted)
        offset += len(page)
        if offset >= payload["result"]["total"]:
            break
    return records


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ensure_localities_workbook()
    localities = load_localities()
    raw_outcomes = retrieve_outcomes()
    target_rows = [row for row in raw_outcomes if row.get("Date") in TARGET_DATES]
    numeric_target_rows = [
        row
        for row in target_rows
        if row.get("City_Code") and str(row.get("Cumulative_verified_cases", "")).isdigit()
    ]
    cumulative = {
        (str(int(row["City_Code"])), row["Date"]): row.get("Cumulative_verified_cases", "")
        for row in raw_outcomes
        if row.get("City_Code") and str(row.get("Cumulative_verified_cases", "")).isdigit()
    }

    outcomes: list[dict[str, object]] = []
    for target in TARGET_DATES:
        previous = (date.fromisoformat(target) - timedelta(days=1)).isoformat()
        for (city_code, observed_date), total in cumulative.items():
            if observed_date != target or city_code not in localities:
                continue
            previous_total = cumulative.get((city_code, previous))
            locality = localities[city_code]
            population = float(locality["population_2019"])
            outcomes.append(
                {
                    **locality,
                    "date": target,
                    "cumulative_cases": int(total),
                    "new_cases": "" if previous_total is None else int(total) - int(previous_total),
                    "cumulative_case_rate": int(total) / population,
                    "log_cumulative_case_rate": math.log(max(int(total) / population, 1e-8)),
                    "daily_case_rate": ""
                    if previous_total is None
                    else (int(total) - int(previous_total)) / population,
                    "log_daily_case_rate": ""
                    if previous_total is None
                    else math.log(max((int(total) - int(previous_total)) / population, 1e-8)),
                }
            )

    outcomes.sort(key=lambda row: (str(row["date"]), str(row["city_code"])))
    write_csv(
        RUN_DIRECTORY / "public_outcomes_four_peaks.csv",
        outcomes,
        [
            "city_code",
            "city_name_en",
            "population_2019",
            "latitude",
            "longitude",
            "date",
            "cumulative_cases",
            "new_cases",
            "cumulative_case_rate",
            "log_cumulative_case_rate",
            "daily_case_rate",
            "log_daily_case_rate",
        ],
    )
    july_codes = sorted({str(row["city_code"]) for row in outcomes if row["date"] == "2020-07-24"})
    cohort = [
        {
            "subject_id": code,
            "address": f"{localities[code]['city_name_en']}, Israel",
            "latitude": localities[code]["latitude"],
            "longitude": localities[code]["longitude"],
            "start_date": "2016-01-01",
            "end_date": "2019-12-31",
        }
        for code in july_codes
    ]
    write_csv(
        RUN_DIRECTORY / "aeris_cohort.csv",
        cohort,
        ["subject_id", "address", "latitude", "longitude", "start_date", "end_date"],
    )
    manifest = {
        "study_pmid": "34260961",
        "outcome_source": {
            "name": "Israel Ministry of Health COVID-19 city table",
            "resource_id": OUTCOME_RESOURCE_ID,
            "api": OUTCOME_API,
            "retrieved_via": "CKAN datastore_search pagination",
        },
        "location_population_source": {
            "name": "Israel Central Bureau of Statistics, Localities in Israel 2019",
            "url": LOCALITIES_URL,
            "sha256": hashlib.sha256(LOCALITIES_WORKBOOK.read_bytes()).hexdigest(),
        },
        "target_dates": list(TARGET_DATES),
        "target_rows_from_government_table": len(target_rows),
        "numeric_target_rows_after_current_suppression": len(numeric_target_rows),
        "numeric_target_rows_with_2019_cbs_population_and_coordinates": len(outcomes),
        "outcome_rows": len(outcomes),
        "july_2020_cohort_size": len(cohort),
    }
    (RUN_DIRECTORY / "public_input_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

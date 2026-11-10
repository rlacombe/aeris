#!/usr/bin/env python3
"""Create 11 BHS-region AERIS subjects from public 2010 Census inputs.

Smith and Chi (2023) fixed the Alaska population at its 2010 value and grouped
boroughs/census areas into 11 Behavioral Health System (BHS) regions. The
local AERIS environment has no polygon stack, so this script creates a
population-weighted internal-point coordinate for each documented BHS group.
The resulting point assignment is explicit in the output and does not claim
polygon-wide monitor aggregation.
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / "inputs"
OUTPUTS = ROOT / "outputs"
GAZETTEER_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/county2k.zip"

# 2010 county-equivalent FIPS grouped under the 11 BHS labels cited by the
# paper. Valdez-Cordova (02261) existed during the paper's 2007--2017 frame.
BHS_FIPS = {
    "Anchorage Municipality": ["02020"],
    "Fairbanks North Star Borough": ["02090"],
    "City and Borough of Juneau": ["02110"],
    "Kenai Peninsula Borough": ["02122"],
    "Matanuska-Susitna Borough": ["02170"],
    "Northwest Region": ["02180", "02185", "02188"],
    "Other Interior Region": ["02068", "02240", "02261", "02290"],
    "Other Southeast Region - Northern": ["02100", "02232", "02280", "02220", "02282"],
    "Other Southeast Region - Southern": ["02130", "02201"],
    "Y-K Delta Region": ["02050", "02270"],
    "Southwest Region": ["02013", "02016", "02060", "02070", "02150", "02164"],
}


def retrieve(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "AERIS-reproduction/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def main() -> None:
    INPUTS.mkdir(exist_ok=True)
    OUTPUTS.mkdir(exist_ok=True)
    gazetteer_path = INPUTS / "2010_Gaz_counties_national.txt"
    if not gazetteer_path.exists():
        import zipfile

        archive = INPUTS / "county2k.zip"
        archive.write_bytes(retrieve(GAZETTEER_URL))
        with zipfile.ZipFile(archive) as bundle:
            name = next(item for item in bundle.namelist() if item.endswith(".txt"))
            gazetteer_path.write_bytes(bundle.read(name))

    # The 2010 Gazetteer is a fixed-width file. Its Alaska rows carry the
    # county-equivalent name, 2010 population, and Census internal point.
    leading_pattern = re.compile(r"^AK(?P<geoid>\d{5})(?P<name>.{60})(?P<population>\s*\d+)")
    coordinate_pattern = re.compile(r"(?P<latitude>-?[\d.]+)(?P<longitude>-\d+\.\d+)\s*$")
    county_population = {}
    county_points = {}
    for line in gazetteer_path.read_text(encoding="latin-1").splitlines():
        leading = leading_pattern.match(line)
        coordinates = coordinate_pattern.search(line)
        if not leading or not coordinates:
            continue
        geoid = leading.group("geoid")
        county_population[geoid] = {
            "name": leading.group("name").strip(),
            "population": int(leading.group("population")),
        }
        county_points[geoid] = (float(coordinates.group("latitude")), float(coordinates.group("longitude")))

    membership_rows = []
    subjects = []
    assigned = set()
    for order, (region, fipses) in enumerate(BHS_FIPS.items(), start=1):
        weighted_latitude = weighted_longitude = 0.0
        total_population = 0
        for fips in fipses:
            if fips not in county_population or fips not in county_points:
                raise RuntimeError(f"Missing Census population or internal point for {fips} ({region})")
            population = county_population[fips]["population"]
            latitude, longitude = county_points[fips]
            total_population += population
            weighted_latitude += population * latitude
            weighted_longitude += population * longitude
            membership_rows.append(
                {"region": region, "order": order, "geoid10": fips, "name10": county_population[fips]["name"], "population_2010": population}
            )
            assigned.add(fips)
        subjects.append(
            {
                "subject_id": f"bhs_{order:02d}",
                "region": region,
                "latitude": f"{weighted_latitude / total_population:.6f}",
                "longitude": f"{weighted_longitude / total_population:.6f}",
                "population_2010": total_population,
                "start_date": "2007-01-01",
                "end_date": "2017-12-31",
            }
        )
    if assigned != set(county_population):
        raise RuntimeError(f"Unassigned Alaska county equivalents: {sorted(set(county_population) - assigned)}")

    def write_csv(path: Path, rows: list[dict]) -> None:
        columns = list(rows[0])
        lines = [",".join(columns)]
        for row in rows:
            lines.append(",".join(str(row[column]).replace(",", " ") for column in columns))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    write_csv(OUTPUTS / "bhs_region_membership.csv", membership_rows)
    write_csv(OUTPUTS / "bhs_region_subjects.csv", subjects)
    manifest = {
        "accessed_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gazetteer_url": GAZETTEER_URL,
        "regions": len(subjects),
        "county_equivalents": len(membership_rows),
        "subject_location_method": "2010-population-weighted mean of county-equivalent Census internal points",
    }
    (OUTPUTS / "geography_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

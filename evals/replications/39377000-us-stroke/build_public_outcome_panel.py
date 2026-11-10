#!/usr/bin/env python3
"""Build a public 2019 county ischemic-stroke outcome panel for PMID 39377000.

This uses the NCHS public-use mortality file rather than the study's exposure
data. Public-use records identify counties that had at least 100,000 residents
in the 2000 Census; records from all other counties have county code 999 and
are outside this reproducible subset.
"""

from __future__ import annotations

import csv
import io
import json
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path


RUN_DIR = Path(__file__).resolve().parent
SOURCE_DIR = RUN_DIR / "public-mortality-source"
ARCHIVE = SOURCE_DIR / "mort2019us_fresh.zip"
MEMBER = "VS19MORT.DUSMCPUB_r20210304"
POPULATION_BASE_URL = (
    "https://www2.census.gov/programs-surveys/popest/datasets/2010-2019/"
    "counties/asrh/cc-est2019-agesex-"
)
POPULATION_SOURCE_DIR = RUN_DIR / "public-population-source"


def county_deaths() -> Counter[str]:
    """Return 2019 I63 deaths at age 65+ for identifiable US counties."""
    counts: Counter[str] = Counter()
    with zipfile.ZipFile(ARCHIVE) as archive:
        with archive.open(MEMBER) as raw:
            for line in io.TextIOWrapper(raw, encoding="ascii", errors="replace"):
                # Fixed columns use 1-based locations from the NCHS record layout.
                state = line[28:30]
                county = line[34:37]
                age_recode_52 = line[74:76]
                icd10 = line[145:149].strip()
                if (
                    state.isdigit()
                    and state not in {"00", "72"}
                    and county.isdigit()
                    and county != "999"
                    and age_recode_52.isdigit()
                    and int(age_recode_52) >= 39
                    and icd10 == "I63"
                ):
                    counts[state + county] += 1
    return counts


def census_populations(states: set[str]) -> dict[str, tuple[str, int]]:
    """Return July 1, 2019 county 65+ population denominators from Census PEP."""
    POPULATION_SOURCE_DIR.mkdir(exist_ok=True)
    populations: dict[str, tuple[str, int]] = {}
    for state in sorted(states):
        source = POPULATION_SOURCE_DIR / f"cc-est2019-agesex-{state}.csv"
        if not source.exists():
            with urllib.request.urlopen(POPULATION_BASE_URL + f"{state}.csv", timeout=90) as response:
                source.write_bytes(response.read())
        with source.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                # YEAR=12 is the July 1, 2019 estimate; see the Census layout.
                if row["SUMLEV"] != "050" or row["YEAR"] != "12":
                    continue
                fips = row["STATE"].zfill(2) + row["COUNTY"].zfill(3)
                populations[fips] = (row["CTYNAME"] + ", " + row["STNAME"], int(row["AGE65PLUS_TOT"]))
    return populations


def main() -> None:
    if not ARCHIVE.is_file():
        raise FileNotFoundError(
            f"Missing {ARCHIVE}. Download the source file listed in README.md first."
        )
    deaths = county_deaths()
    populations = census_populations({fips[:2] for fips in deaths})
    output = RUN_DIR / "public_2019_ischemic_stroke_65plus_counties.csv"
    rows = []
    for fips, death_count in sorted(deaths.items()):
        if fips not in populations:
            continue
        county_name, population_65plus = populations[fips]
        if population_65plus <= 0:
            continue
        rows.append(
            {
                "fips": fips,
                "county_name": county_name,
                "year": 2019,
                "ischemic_stroke_deaths_65plus": death_count,
                "population_65plus_acs5": population_65plus,
                "crude_rate_per_100k_65plus": round(death_count * 100000 / population_65plus, 6),
            }
        )
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "mortality_source": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/DVS/mortality/mort2019us.zip",
        "mortality_member": MEMBER,
        "cause": "ICD-10 I63 (cerebral infarction)",
        "age": "65 years and older (NCHS age recode 52 values 39-51)",
        "geography": "county of residence, counties separately identified in public-use file",
        "denominator_source": POPULATION_BASE_URL + "[state FIPS].csv",
        "n_counties": len(rows),
    }
    (RUN_DIR / "public_outcome_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"n_counties": len(rows), "output": str(output)}))


if __name__ == "__main__":
    main()

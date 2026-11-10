"""Download and construct public non-exposure inputs for PMID 33484722.

This script never retrieves the authors' PM2.5 data.  It records raw WHO and
World Bank responses so the downstream fit can be rebuilt without manual data
collection.  GDP per capita is sourced from the World Bank here as a public
substitute for the OECD GDP series used by the paper.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import pandas as pd

from run_aeris_tools import COUNTRIES


RUN_DIRECTORY = Path(__file__).resolve().parent
INPUT_DIRECTORY = RUN_DIRECTORY / "public-inputs"
WHO_URL = "https://srhdpeuwpubsa.blob.core.windows.net/whdh/COVID/WHO-COVID-19-global-data.csv"
WORLD_BANK = "https://api.worldbank.org/v2/country/all/indicator/{indicator}?date={years}&format=json&per_page=400"
ISO2 = {
    "AUS": "AU", "AUT": "AT", "BEL": "BE", "CAN": "CA", "CHL": "CL", "CZE": "CZ",
    "DNK": "DK", "EST": "EE", "FIN": "FI", "FRA": "FR", "DEU": "DE", "GRC": "GR",
    "HUN": "HU", "ISL": "IS", "IRL": "IE", "ISR": "IL", "ITA": "IT", "JPN": "JP",
    "KOR": "KR", "LVA": "LV", "LTU": "LT", "LUX": "LU", "MEX": "MX", "NLD": "NL",
    "NZL": "NZ", "NOR": "NO", "POL": "PL", "PRT": "PT", "SVK": "SK", "SVN": "SI",
    "ESP": "ES", "SWE": "SE", "CHE": "CH", "TUR": "TR", "GBR": "GB", "USA": "US",
}
INDICATORS = {
    "population": ("SP.POP.TOTL", "2019"),
    "older_65_pct": ("SP.POP.65UP.TO.ZS", "2018"),
    "physicians_per_1000": ("SH.MED.PHYS.ZS", "2015:2017"),
    "hospital_beds_per_1000": ("SH.MED.BEDS.ZS", "2012:2015"),
    "surface_area_km2": ("AG.SRF.TOTL.K2", "2019"),
    "gdp_per_capita_usd": ("NY.GDP.PCAP.CD", "2019"),
}


def download(url: str, destination: Path) -> dict[str, object]:
    with urlopen(url, timeout=90) as response:  # nosec B310 -- fixed public HTTPS sources
        body = response.read()
    destination.write_bytes(body)
    return {
        "url": url,
        "path": destination.name,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }


def world_bank_values(path: Path) -> dict[str, list[tuple[int, float]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload[1] if len(payload) > 1 and payload[1] else []
    values: dict[str, list[tuple[int, float]]] = {}
    for row in rows:
        iso3 = row.get("countryiso3code")
        value = row.get("value")
        if iso3 in COUNTRIES and value is not None:
            values.setdefault(iso3, []).append((int(row["date"]), float(value)))
    return values


def choose(values: dict[str, list[tuple[int, float]]], iso3: str, preferred: list[int]) -> float | None:
    available = dict(values.get(iso3, []))
    for year in preferred:
        if year in available:
            return available[year]
    return None


def choose_max(values: dict[str, list[tuple[int, float]]], iso3: str, years: list[int]) -> float | None:
    available = dict(values.get(iso3, []))
    candidates = [available[year] for year in years if year in available]
    return max(candidates) if candidates else None


def build_outcomes(who_csv: Path, population: dict[str, list[tuple[int, float]]]) -> pd.DataFrame:
    who = pd.read_csv(who_csv, parse_dates=["Date_reported"])
    rows: list[dict[str, object]] = []
    for iso3, country in COUNTRIES.items():
        country_rows = who.loc[who["Country_code"].eq(ISO2[iso3])].sort_values("Date_reported")
        detected = country_rows.loc[country_rows["New_cases"].gt(0), "Date_reported"]
        if detected.empty:
            continue
        first_case = detected.iloc[0]
        population_2019 = choose(population, iso3, [2019])
        for day in (60, 80):
            target = first_case + pd.Timedelta(days=day)
            # WHO's current global extract reports this early period weekly,
            # whereas the study used daily situation reports.  Retain the
            # study's event-time definition and select the first reported
            # cumulative total at or after the requested day.
            matched = country_rows.loc[country_rows["Date_reported"].ge(target)].head(1)
            if matched.empty or population_2019 is None:
                continue
            value = matched.iloc[0]
            rows.append(
                {
                    "iso3": iso3,
                    "country": country,
                    "first_case_date": first_case.date().isoformat(),
                    "event_day": day,
                    "target_date": target.date().isoformat(),
                    "observed_date": value["Date_reported"].date().isoformat(),
                    "observed_event_day": int((value["Date_reported"] - first_case).days),
                    "cumulative_cases": float(value["Cumulative_cases"]),
                    "cumulative_deaths": float(value["Cumulative_deaths"]),
                    "population_2019": population_2019,
                    "case_rate_per_100k": 100000 * float(value["Cumulative_cases"]) / population_2019,
                    "death_rate_per_100k": 100000 * float(value["Cumulative_deaths"]) / population_2019,
                }
            )
    return pd.DataFrame(rows)


def main() -> int:
    INPUT_DIRECTORY.mkdir(exist_ok=True)
    manifest: dict[str, object] = {
        "accessed_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": [],
        "notes": {
            "outcomes": "WHO global CSV; current archived-history file, rather than the paper's June 2020 snapshot.",
            "gdp": "World Bank GDP per capita (current US$) is a documented public source substitution for the OECD GDP input.",
        },
    }
    who_path = INPUT_DIRECTORY / "WHO-COVID-19-global-data.csv"
    manifest["sources"].append(download(WHO_URL, who_path))

    extracted: dict[str, dict[str, list[tuple[int, float]]]] = {}
    for name, (indicator, years) in INDICATORS.items():
        url = WORLD_BANK.format(indicator=indicator, years=years)
        path = INPUT_DIRECTORY / f"world-bank-{name}.json"
        manifest["sources"].append(download(url, path))
        extracted[name] = world_bank_values(path)

    covariate_rows = []
    for iso3, country in COUNTRIES.items():
        area = choose(extracted["surface_area_km2"], iso3, [2019])
        population = choose(extracted["population"], iso3, [2019])
        covariate_rows.append(
            {
                "iso3": iso3,
                "country": country,
                "older_65_pct_2018": choose(extracted["older_65_pct"], iso3, [2018]),
                "population_2019": population,
                "surface_area_km2_2019": area,
                "density_per_km2": population / area if population and area else None,
                "gdp_per_capita_usd_2019": choose(extracted["gdp_per_capita_usd"], iso3, [2019]),
                "physicians_per_1000": choose(extracted["physicians_per_1000"], iso3, [2017, 2016, 2015])
                or choose_max(extracted["physicians_per_1000"], iso3, [2017, 2016, 2015]),
                "hospital_beds_per_1000": choose(extracted["hospital_beds_per_1000"], iso3, [2015, 2014])
                or choose_max(extracted["hospital_beds_per_1000"], iso3, [2013, 2012]),
            }
        )
    pd.DataFrame(covariate_rows).to_csv(INPUT_DIRECTORY / "country_covariates.csv", index=False)
    build_outcomes(who_path, extracted["population"]).to_csv(
        INPUT_DIRECTORY / "country_outcomes_event_days.csv", index=False
    )
    (INPUT_DIRECTORY / "source_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"countries": len(covariate_rows), "outcome_rows": 72}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Reconstruct the Zhou et al. county-day PM2.5 panel with AERIS/OpenAQ.

The script downloads only the source package's public county boundaries and
COVID-19 outcomes. It excludes every author-provided pollution, smoke,
wildfire, weather, mobility, and merged analysis file. PM2.5 comes from the
OpenAQ API through AERIS's rate-limited client, with the public OpenAQ S3
archive as a fallback for missing API days.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import struct
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd
import statsmodels.api as sm
from dotenv import load_dotenv
from patsy import dmatrix

from aeris.exposure.api_clients import OpenAQArchiveClient, RateLimitedOpenAQ
from aeris.exposure.config import Config


RUN = Path(__file__).resolve().parent
SOURCE_COMMIT = "588cd8e0b4d2296a0c599f394a458cb2f7d7b281"
BASE_URL = f"https://raw.githubusercontent.com/xiaodan-zhou/covid_wildfire/{SOURCE_COMMIT}/data"
START = pd.Timestamp("2020-03-15")
END = pd.Timestamp("2020-12-16")
STATES = {"06", "41", "53"}
SEARCH_RADIUS_KM = 100
MIN_DAILY_COVERAGE = 0.75
LAG_DAYS = 28
MAX_MONITORS = int(os.getenv("AERIS_MAX_MONITORS", "24"))
USE_S3_FALLBACK = os.getenv("AERIS_USE_S3_FALLBACK", "false").lower() in {"1", "true", "yes"}

INPUTS = {
    "covid_confirmed_usafacts_Feb6_2021.csv": f"{BASE_URL}/covid_confirmed_usafacts_Feb6_2021.csv",
    "covid_deaths_usafacts_Feb6_2021.csv": f"{BASE_URL}/covid_deaths_usafacts_Feb6_2021.csv",
    "covid_county_population_usafacts_Feb6_2021.csv": f"{BASE_URL}/covid_county_population_usafacts_Feb6_2021.csv",
    "FIPS.csv": f"{BASE_URL}/FIPS.csv",
    "cb_2018_us_county_5m.shp": f"{BASE_URL}/cb_2018_us_county_5m/cb_2018_us_county_5m.shp",
    "cb_2018_us_county_5m.dbf": f"{BASE_URL}/cb_2018_us_county_5m/cb_2018_us_county_5m.dbf",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download(path: Path, url: str) -> None:
    if path.exists():
        return
    request = Request(url, headers={"User-Agent": "AERIS-reproduction/1.0"})
    with urlopen(request, timeout=90) as response, path.open("wb") as output:
        shutil.copyfileobj(response, output)


def dbf_records(path: Path) -> list[dict[str, str]]:
    data = path.read_bytes()
    n_records, header_length, record_length = struct.unpack("<xxxxIHH20x", data[:32])
    fields, offset = [], 32
    while data[offset] != 0x0D:
        raw = data[offset : offset + 32]
        fields.append((raw[:11].split(b"\0")[0].decode("ascii"), raw[16]))
        offset += 32
    rows = []
    for index in range(n_records):
        record = data[header_length + index * record_length : header_length + (index + 1) * record_length]
        if record[:1] == b"*":
            continue
        row, position = {}, 1
        for name, width in fields:
            row[name] = record[position : position + width].decode("latin1").strip()
            position += width
        rows.append(row)
    return rows


def shp_centroids(path: Path) -> list[tuple[float, float]]:
    """Return bounding-box centroids in the order of the source shapefile."""
    data, offset, centroids = path.read_bytes(), 100, []
    while offset < len(data):
        _number, words = struct.unpack(">2i", data[offset : offset + 8])
        content = data[offset + 8 : offset + 8 + words * 2]
        offset += 8 + words * 2
        kind = struct.unpack("<i", content[:4])[0]
        if kind == 0:
            centroids.append((math.nan, math.nan))
            continue
        xmin, ymin, xmax, ymax = struct.unpack("<4d", content[4:36])
        centroids.append(((ymin + ymax) / 2, (xmin + xmax) / 2))
    return centroids


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    value = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return radius * 2 * math.asin(math.sqrt(value))


def source_inputs() -> tuple[pd.DataFrame, dict]:
    raw = RUN / "source_inputs"
    raw.mkdir(exist_ok=True)
    manifest = []
    for name, url in INPUTS.items():
        path = raw / name
        download(path, url)
        manifest.append({"file": str(path.relative_to(RUN)), "url": url, "sha256": sha256(path), "bytes": path.stat().st_size})

    attributes = dbf_records(raw / "cb_2018_us_county_5m.dbf")
    centroids = shp_centroids(raw / "cb_2018_us_county_5m.shp")
    fips_frame = pd.read_csv(raw / "FIPS.csv", dtype=str)
    eligible_fips = set(
        fips_frame["FIPS"].str.replace(r"\.0$", "", regex=True).str.zfill(5).loc[
            lambda values: values.str[:2].isin(STATES) & values.str[-3:].ne("000")
        ]
    )
    geography = pd.DataFrame(
        [
            {"fips": f"{row['STATEFP']}{row['COUNTYFP']}", "county": row["NAME"], "latitude": centroid[0], "longitude": centroid[1]}
            for row, centroid in zip(attributes, centroids)
            if f"{row['STATEFP']}{row['COUNTYFP']}" in eligible_fips
        ]
    )
    if len(geography) != 133:
        raise RuntimeError(f"expected 133 CA/OR/WA counties, found {len(geography)}")

    outcomes = None
    for value_name, filename in (("cases", "covid_confirmed_usafacts_Feb6_2021.csv"), ("deaths", "covid_deaths_usafacts_Feb6_2021.csv")):
        frame = pd.read_csv(raw / filename, dtype={"countyFIPS": str})
        frame["fips"] = frame["countyFIPS"].fillna("").str.replace(r"\.0$", "", regex=True).str.zfill(5)
        columns = [column for column in frame if column.startswith("2020/")]
        long = frame[frame.fips.isin(eligible_fips)].melt(id_vars="fips", value_vars=columns, var_name="date", value_name="cumulative")
        long["date"] = pd.to_datetime(long["date"], format="%Y/%m/%d")
        long = long[(long.date >= START) & (long.date <= END)].sort_values(["fips", "date"])
        long[value_name] = long.groupby("fips")["cumulative"].diff().fillna(long["cumulative"])
        long = long[["fips", "date", value_name]]
        outcomes = long if outcomes is None else outcomes.merge(long, on=["fips", "date"], validate="one_to_one")
    population = pd.read_csv(raw / "covid_county_population_usafacts_Feb6_2021.csv", dtype={"countyFIPS": str})
    population["fips"] = population["countyFIPS"].fillna("").str.replace(r"\.0$", "", regex=True).str.zfill(5)
    pop_column = next(column for column in population if column.lower() == "population")
    population = population[population.fips.isin(eligible_fips)].drop_duplicates("fips")
    outcomes = outcomes.merge(population[["fips", pop_column]].rename(columns={pop_column: "population"}), on="fips", how="left", validate="many_to_one")
    return geography, {"files": manifest, "outcomes": outcomes}


def location_catalog(client: RateLimitedOpenAQ) -> pd.DataFrame:
    """Load the western-US monitor catalog with three bounded requests."""
    boxes = [(-124.9, 32.0, -114.0, 42.2), (-124.9, 41.9, -116.4, 46.4), (-124.9, 45.5, -116.8, 49.1)]
    locations = {}
    for bbox in boxes:
        page = 1
        while True:
            response = client.list_locations(bbox=bbox, limit=1000, page=page)
            records = list(response.results or [])
            for record in records:
                parameters = {sensor.parameter.name.lower() for sensor in (record.sensors or [])}
                if record.datetime_first is None or record.datetime_last is None:
                    continue
                first = pd.Timestamp(record.datetime_first.utc)
                last = pd.Timestamp(record.datetime_last.utc)
                if "pm25" in parameters and first <= END.tz_localize("UTC") and last >= START.tz_localize("UTC"):
                    locations[record.id] = record
            if len(records) < 1000:
                break
            page += 1
    rows = []
    for record in locations.values():
        sensor = next(sensor for sensor in record.sensors if sensor.parameter.name.lower() == "pm25")
        rows.append({"location_id": record.id, "sensor_id": sensor.id, "name": record.name, "latitude": record.coordinates.latitude, "longitude": record.coordinates.longitude})
    catalog = pd.DataFrame(rows).drop_duplicates("location_id")
    if catalog.empty:
        raise RuntimeError("OpenAQ catalog yielded no eligible western-US PM2.5 monitors")
    return catalog


def select_monitors(geography: pd.DataFrame, catalog: pd.DataFrame) -> pd.DataFrame:
    assignments = []
    for county in geography.itertuples(index=False):
        distances = catalog.apply(lambda monitor: haversine_km(county.latitude, county.longitude, monitor.latitude, monitor.longitude), axis=1)
        idx = distances.idxmin()
        monitor = catalog.loc[idx]
        assignments.append({"fips": county.fips, "county": county.county, "county_latitude": county.latitude, "county_longitude": county.longitude, **monitor.to_dict(), "distance_km": float(distances.loc[idx]), "within_radius": bool(distances.loc[idx] <= SEARCH_RADIUS_KM)})
    return pd.DataFrame(assignments)


def bounded_assignments(assignments: pd.DataFrame, outcomes: pd.DataFrame) -> pd.DataFrame:
    """Predeclare a practical first panel using population, never exposure values."""
    if MAX_MONITORS <= 0:
        return assignments
    population = outcomes[["fips", "population"]].drop_duplicates("fips")
    ranked = assignments.merge(population, on="fips", how="left").sort_values("population", ascending=False)
    selected = ranked[ranked.within_radius].drop_duplicates("location_id").head(MAX_MONITORS)
    return assignments[assignments.location_id.isin(selected.location_id)].copy()


def fetch_daily(client: RateLimitedOpenAQ, assignments: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retrieve each selected AERIS/OpenAQ monitor once; use S3 for missing days."""
    archive = OpenAQArchiveClient(timeout=(5.0, 45.0), max_retries=3)
    expected = pd.date_range(START, END, freq="D")
    series, audit = [], []
    for monitor in assignments[assignments.within_radius].drop_duplicates("location_id").itertuples(index=False):
        rows, page = [], 1
        while True:
            response = client.list_daily_measurements(sensor_id=int(monitor.sensor_id), date_from=START.date().isoformat(), date_to=END.date().isoformat(), limit=1000, page=page)
            batch = list(response.results or [])
            rows.extend(batch)
            if len(batch) < 1000:
                break
            page += 1
        values = {}
        for row in rows:
            day = pd.Timestamp(row.period.datetime_from.utc).normalize().tz_localize(None)
            values[day] = float(row.value)
        missing = [item.date() for item in expected if item not in values]
        archive_values, archive_errors = {}, []
        if missing and USE_S3_FALLBACK:
            available = archive.list_available_dates(int(monitor.location_id), min(missing), max(missing))
            recovered = archive.fetch_daily_range(int(monitor.location_id), min(missing), max(missing), parameter="pm25", available_dates=available, max_workers=4)
            archive_errors = list(archive.last_errors)
            archive_values = {pd.Timestamp(item["period"]["datetime_from"]["utc"]).normalize().tz_localize(None): float(item["value"]) for item in recovered}
            values.update(archive_values)
        for day, value in values.items():
            if START <= day <= END:
                series.append({"location_id": monitor.location_id, "date": day, "pm25": value, "source": "openaq_api" if day not in archive_values else "openaq_archive_s3"})
        audit.append({"location_id": monitor.location_id, "sensor_id": monitor.sensor_id, "api_days": len(rows), "archive_days": len(archive_values), "retrieved_days": len(values), "archive_errors": len(archive_errors)})
    return pd.DataFrame(series), pd.DataFrame(audit)


def fit(panel: pd.DataFrame, outcome: str) -> dict:
    model_data = panel[["fips", "date", outcome, "population", "pm25"]].copy().sort_values(["fips", "date"])
    lags = [model_data.groupby("fips")["pm25"].shift(value) for value in range(LAG_DAYS + 1)]
    model_data["pm25_lag_0_28"] = pd.concat(lags, axis=1).mean(axis=1)
    model_data = model_data.dropna(subset=["pm25_lag_0_28", outcome, "population"])
    model_data["day"] = (model_data.date - model_data.date.min()).dt.days
    time_basis = dmatrix("bs(day, df=6, include_intercept=False)", model_data, return_type="dataframe")
    county_basis = pd.get_dummies(model_data["fips"], prefix="county", drop_first=True, dtype=float)
    design = pd.concat([pd.Series(1.0, index=model_data.index, name="intercept"), model_data[["pm25_lag_0_28"]], time_basis.set_index(model_data.index), county_basis.set_index(model_data.index)], axis=1)
    fitted = sm.GLM(model_data[outcome].astype(float), design.astype(float), family=sm.families.Poisson(), offset=np.log(model_data.population.astype(float))).fit(cov_type="cluster", cov_kwds={"groups": model_data.fips})
    coefficient = float(fitted.params["pm25_lag_0_28"])
    interval = fitted.conf_int().loc["pm25_lag_0_28"].astype(float)
    return {"outcome": outcome, "rows": int(len(model_data)), "counties": int(model_data.fips.nunique()), "days": int(model_data.date.nunique()), "ratio_per_10_ug_m3": float(math.exp(10 * coefficient)), "ci95": [float(math.exp(10 * interval.iloc[0])), float(math.exp(10 * interval.iloc[1]))], "coefficient_per_ug_m3": coefficient, "model": "Poisson log-linear county-day model with log(population) offset, county fixed effects, and 6-df calendar-time spline; PM2.5 is the county-centroid nearest-monitor 28-day mean."}


def main() -> None:
    load_dotenv(".env")
    config = Config.from_env()
    if not config.openaq_api_key:
        raise RuntimeError("OPENAQ_API_KEY is required for the AERIS/OpenAQ reconstruction")
    client = RateLimitedOpenAQ(config.openaq_api_key, config)
    geography, inputs = source_inputs()
    catalog = location_catalog(client)
    assignments = select_monitors(geography, catalog)
    selected_assignments = bounded_assignments(assignments, inputs["outcomes"])
    output = RUN / "outputs"
    output.mkdir(exist_ok=True)
    catalog.to_csv(output / "openaq_western_us_pm25_catalog.csv", index=False)
    assignments.to_csv(output / "county_monitor_assignment.csv", index=False)
    selected_assignments.to_csv(output / "selected_county_monitor_assignment.csv", index=False)
    exposure, retrieval_audit = fetch_daily(client, selected_assignments)
    panel = inputs["outcomes"].merge(selected_assignments[selected_assignments.within_radius][["fips", "location_id", "distance_km"]], on="fips", how="inner").merge(exposure, on=["location_id", "date"], how="left")
    coverage = panel.groupby("fips").pm25.agg([("observed_days", "count"), ("mean_pm25", "mean")]).reset_index()
    coverage["coverage"] = coverage.observed_days / len(pd.date_range(START, END))
    retained = set(coverage.loc[coverage.coverage >= MIN_DAILY_COVERAGE, "fips"])
    panel = panel[panel.fips.isin(retained)].copy()
    retrieval_audit.to_csv(output / "monitor_retrieval_audit.csv", index=False)
    coverage.to_csv(output / "county_coverage.csv", index=False)
    panel.to_csv(output / "county_day_panel.csv", index=False)
    result = {"status": "insufficient_coverage", "retained_counties": len(retained), "candidate_counties": len(geography), "selected_counties": int(selected_assignments.fips.nunique()), "selected_monitors": int(selected_assignments.location_id.nunique()), "period_days": len(pd.date_range(START, END)), "search_radius_km": SEARCH_RADIUS_KM, "minimum_daily_coverage": MIN_DAILY_COVERAGE}
    if retained:
        result["cases"] = fit(panel, "cases")
        result["deaths"] = fit(panel, "deaths")
        result["status"] = "fitted"
    (output / "model_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = {"study": {"pmid": "34389545", "doi": "10.1126/sciadv.abi8789", "source_commit": SOURCE_COMMIT, "period": [START.date().isoformat(), END.date().isoformat()]}, "source_policy": "The author package supplied only county identifiers, county geometry, population, and COVID-19 outcomes. The reconstruction does not download, read, or use author PM2.5, wildfire, smoke, weather, mobility, or merged-analysis fields.", "aeris_exposure": {"provider": "OpenAQ API", "s3_fallback_enabled": USE_S3_FALLBACK, "pollutant": "pm25", "assignment": f"nearest catalogued historical PM2.5 monitor to county bounding-box centroid within {SEARCH_RADIUS_KM} km", "aggregation": "daily monitor value then 28-day mean", "catalog_monitors": int(len(catalog)), "assigned_counties": int(assignments.within_radius.sum()), "selected_counties": int(selected_assignments.fips.nunique()), "selected_monitors": int(selected_assignments.location_id.nunique()), "selection": "The first runnable panel retains counties served by the 24 monitors selected from highest-population counties before exposure retrieval. Set AERIS_MAX_MONITORS=0 to retrieve all assignments.", "retained_counties": int(len(retained))}, "source_inputs": inputs["files"], "outputs": {"result": "outputs/model_result.json", "panel": "outputs/county_day_panel.csv", "coverage": "outputs/county_coverage.csv", "assignment": "outputs/county_monitor_assignment.csv", "selected_assignment": "outputs/selected_county_monitor_assignment.csv", "retrieval_audit": "outputs/monitor_retrieval_audit.csv"}}
    (RUN / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

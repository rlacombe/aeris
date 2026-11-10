from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pandas as pd
from shapely.geometry import Point, shape


ROOT = Path(__file__).resolve().parent
START, END = "2020-03-26", "2020-09-15"


def read_ecad(zf: zipfile.ZipFile, member: str, value: str) -> pd.DataFrame:
    text = zf.read(member).decode("latin-1")
    header = next(i for i, line in enumerate(text.splitlines()) if line.startswith("STAID,"))
    data = pd.read_csv(io.StringIO(text), skiprows=header)
    data["date"] = pd.to_datetime(data["    DATE"] if "    DATE" in data else data["DATE"], format="%Y%m%d")
    value_col = next(column for column in data if column.strip() == value)
    quality_col = next(column for column in data if column.strip() == f"Q_{value}")
    return data.loc[(data["date"] >= START) & (data["date"] <= END) & (data[quality_col] == 0), ["date", value_col]].rename(columns={value_col: value})


def main() -> None:
    boundary = json.loads((ROOT / "boundaries.geojson").read_text())
    polygons = [(feature["properties"]["shapeName"], shape(feature["geometry"])) for feature in boundary["features"]]
    with zipfile.ZipFile(ROOT / "weather-source/ECA_blend_tg.zip") as tg_zip:
        station_text = tg_zip.read("stations.txt").decode("latin-1")
        header = next(i for i, line in enumerate(station_text.splitlines()) if line.startswith("STAID,"))
        stations = pd.read_csv(io.StringIO(station_text), skiprows=header)
        stations.columns = [column.strip() for column in stations.columns]
        stations = stations.loc[stations["CN"].str.strip() == "GB"].copy()
        stations["STAID"] = stations["STAID"].astype(int)
        def country(row):
            lat = float(row["LAT"].replace("+", "").split(":" )[0]) + float(row["LAT"].split(":" )[1]) / 60
            lon_sign = -1 if row["LON"].startswith("-") else 1
            lon_parts = row["LON"].replace("+", "").replace("-", "").split(":")
            lon = lon_sign * (float(lon_parts[0]) + float(lon_parts[1]) / 60)
            point = Point(lon, lat)
            return next((name for name, polygon in polygons if polygon.contains(point)), None)
        stations["area_name"] = stations.apply(country, axis=1)
        stations = stations.dropna(subset=["area_name"])
        tg = []
        for station in stations.itertuples():
            member = f"TG_STAID{station.STAID:06d}.txt"
            if member in tg_zip.namelist():
                frame = read_ecad(tg_zip, member, "TG")
                frame["area_name"] = station.area_name
                tg.append(frame)
    with zipfile.ZipFile(ROOT / "weather-source/ECA_blend_ss.zip") as ss_zip:
        ss = []
        names = set(ss_zip.namelist())
        for station in stations.itertuples():
            member = f"SS_STAID{station.STAID:06d}.txt"
            if member in names:
                frame = read_ecad(ss_zip, member, "SS")
                frame["area_name"] = station.area_name
                ss.append(frame)
    temperature = pd.concat(tg).groupby(["area_name", "date"], as_index=False)["TG"].mean()
    temperature["temperature_c"] = temperature["TG"] / 10
    sunshine = pd.concat(ss).groupby(["area_name", "date"], as_index=False)["SS"].mean()
    sunshine["sunshine_hours"] = sunshine["SS"] / 10
    weather = temperature.merge(sunshine, on=["area_name", "date"], how="outer").sort_values(["area_name", "date"])
    weather["temperature_c"] = weather.groupby("area_name")["temperature_c"].transform(lambda s: s.fillna(s.rolling(7, min_periods=1).mean()))
    weather[["area_name", "date", "temperature_c", "sunshine_hours"]].to_csv(ROOT / "ecad_weather_nation_day.csv", index=False)
    (ROOT / "ecad_weather_manifest.json").write_text(json.dumps({"temperature_stations": len(tg), "sunshine_stations": len(ss), "uk_stations": len(stations)}, indent=2) + "\n")


if __name__ == "__main__":
    main()

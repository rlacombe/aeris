"""Validate and merge checkpointed AERIS daily and station outputs."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


RUN_DIRECTORY = Path(__file__).resolve().parent
CHUNK_DIRECTORY = RUN_DIRECTORY / "chunks"


def read_nonempty(pattern: str) -> list[pd.DataFrame]:
    frames = []
    for path in sorted(CHUNK_DIRECTORY.glob(pattern)):
        if path.stat().st_size:
            frames.append(pd.read_csv(path))
    return frames


def main() -> int:
    daily_frames = read_nonempty("*_daily.csv")
    station_frames = read_nonempty("*_stations.csv")
    if not daily_frames:
        raise RuntimeError("No non-empty AERIS daily chunk output is available.")
    daily = pd.concat(daily_frames, ignore_index=True)
    daily["date"] = pd.to_datetime(daily["date"])
    duplicate_keys = daily.duplicated(["region", "date"], keep=False)
    if duplicate_keys.any():
        duplicates = daily.loc[duplicate_keys, ["region", "date"]].to_dict(orient="records")
        raise RuntimeError(f"Overlapping daily chunks: {duplicates[:10]}")
    daily = daily.sort_values(["region", "date"]).reset_index(drop=True)
    daily.to_csv(RUN_DIRECTORY / "aeris_pm25_daily.csv", index=False)
    if station_frames:
        stations = pd.concat(station_frames, ignore_index=True).drop_duplicates()
        stations.to_csv(RUN_DIRECTORY / "aeris_station_coverage.csv", index=False)
    coverage = (
        daily.groupby("region", as_index=False)
        .agg(pm25_days=("date", "size"), mean_pm25=("mean", "mean"), mean_daily_stations=("n_stations", "mean"))
    )
    coverage.to_csv(RUN_DIRECTORY / "aeris_chunk_coverage.csv", index=False)
    payload = {"daily_rows": len(daily), "regions": coverage.to_dict(orient="records")}
    (RUN_DIRECTORY / "aeris_chunk_manifest.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

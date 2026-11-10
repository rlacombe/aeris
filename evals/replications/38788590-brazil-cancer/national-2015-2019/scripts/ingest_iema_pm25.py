#!/usr/bin/env python3
"""Build daily PM2.5 monitor-network means from public IEMA state archives."""
from __future__ import annotations

import csv
import io
import json
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "iema"
DERIVED = ROOT / "data" / "derived"


def members(archive: Path) -> list[str]:
    output = subprocess.run(["bsdtar", "-tf", str(archive)], check=True, capture_output=True, text=True).stdout
    return [line.strip() for line in output.splitlines() if line.lower().endswith(".csv")]


def is_pm25(value: object) -> bool:
    token = re.sub(r"[^A-Z0-9]", "", str(value).upper())
    return token in {"MP25", "PM25", "MP2,5"} or "PM25" in token


def number(value: object) -> float | None:
    try:
        parsed = float(str(value).strip().replace(",", "."))
        return parsed if parsed >= 0 else None
    except ValueError:
        return None


def main() -> int:
    manifest = json.loads((RAW / "iema_download_manifest.json").read_text())
    if manifest["failures"]:
        raise RuntimeError("IEMA archive manifest contains failed downloads.")
    hourly: dict[tuple[str, str, str], list[float]] = defaultdict(list)
    file_counts = []
    for record in manifest["records"]:
        archive = Path(record["path"])
        selected_rows = 0
        for member in members(archive):
            process = subprocess.Popen(["bsdtar", "-xOf", str(archive), member], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            assert process.stdout is not None
            reader = csv.DictReader(io.TextIOWrapper(process.stdout, encoding="utf-8-sig", errors="replace"))
            for row in reader:
                date = row.get("Data") or row.get("data") or row.get("DATE")
                pollutant = row.get("Poluente") or row.get("poluente") or row.get("POLLUTANT")
                station = row.get("Codigo") or row.get("Código") or row.get("Estacao") or row.get("Estação") or "unknown"
                value = row.get("Valor") or row.get("valor") or row.get("VALUE")
                if not date or not str(date).startswith(("2015-", "2016-", "2017-", "2018-", "2019-")) or not is_pm25(pollutant):
                    continue
                parsed = number(value)
                if parsed is None:
                    continue
                hourly[(record["uf"], str(station).strip(), str(date).strip())].append(parsed)
                selected_rows += 1
            if process.wait() != 0:
                raise RuntimeError(f"Could not read {archive.name}:{member}")
        file_counts.append({"uf": record["uf"], "archive": archive.name, "selected_pm25_rows": selected_rows})
    station_days = []
    for (uf, station, date), values in hourly.items():
        station_days.append({"date": date, "uf": uf, "station": station, "pm25_ug_m3": sum(values) / len(values), "n_hourly_values": len(values)})
    station_frame = pd.DataFrame(station_days)
    if station_frame.empty:
        raise RuntimeError("No 2015--2019 PM2.5 records were found in IEMA archives.")
    network = station_frame.groupby("date", as_index=False).agg(pm25_ug_m3=("pm25_ug_m3", "mean"), n_stations=("station", "count"), n_states=("uf", "nunique"))
    DERIVED.mkdir(parents=True, exist_ok=True)
    station_frame.to_csv(DERIVED / "iema_pm25_station_daily.csv", index=False)
    network.to_csv(DERIVED / "iema_pm25_national_daily.csv", index=False)
    summary = {"processed_at_utc": datetime.now(timezone.utc).isoformat(), "source": "IEMA standardized state-monitor archives", "files": file_counts,
               "station_days": len(station_frame), "monitor_days": len(network), "states_with_pm25": sorted(station_frame.uf.unique().tolist()),
               "output_station_days": str(DERIVED / "iema_pm25_station_daily.csv"), "output_network": str(DERIVED / "iema_pm25_national_daily.csv")}
    (DERIVED / "iema_pm25_ingestion_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({key: summary[key] for key in ("station_days", "monitor_days", "states_with_pm25")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

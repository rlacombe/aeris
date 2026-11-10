#!/usr/bin/env python3
"""Recover daily CETESB pollutants after the recorded AERIS no-observation result.

Each request is one documented public historical station form request. The
station is inside the AERIS study boundary. It supplies PM2.5, PM10, and NO2
when a corresponding table is present; no missing value is imputed.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
URL = "https://sistemasinter.cetesb.sp.gov.br/Ar/php/ar_dados_horarios_resultado.php"
STATION = "31/Cid.Universitária-USP-Ipen"


def parse_value(table) -> float | None:
    values = []
    for row in table.find_all("tr", recursive=False)[2:]:
        cells = [" ".join(cell.stripped_strings) for cell in row.find_all("td", recursive=False)]
        if len(cells) < 2 or cells[1] == "--":
            continue
        try:
            values.append(float(cells[1].replace(",", ".")))
        except ValueError:
            pass
    return values[-1] if values else None


def parse_tables(payload: bytes) -> dict[str, float | None]:
    result = {"pm25": None, "pm10": None, "no2": None}
    soup = BeautifulSoup(payload, "html.parser")
    for table in soup.find_all("table"):
        rows = table.find_all("tr", recursive=False)
        if not rows:
            continue
        header = " ".join(rows[0].stripped_strings).upper().replace(" ", "")
        for label, column in (("MP2.5", "pm25"), ("MP10", "pm10"), ("NO2", "no2")):
            if header.startswith(label):
                result[column] = parse_value(table)
    return result


def retrieve(day: date) -> tuple[dict[str, float | None], bytes]:
    body = urllib.parse.urlencode({"texData": day.strftime("%d/%m/%Y"), "selEst": STATION}).encode()
    request = urllib.request.Request(URL, data=body, headers={"User-Agent": "AERIS-reproduction/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
    return parse_tables(payload), payload


def main() -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    output = DERIVED / "cetesb_daily_recovery.csv"
    existing = pd.read_csv(output, dtype={"date": str}) if output.exists() else pd.DataFrame(columns=["date", "pm25", "pm10", "no2", "source_station"])
    existing_dates = set(existing.date) if not existing.empty else set()
    records = existing.to_dict("records")
    stream = hashlib.sha256()
    current, end = date(2012, 1, 1), date(2015, 12, 31)
    while current <= end:
        key = current.isoformat()
        if key not in existing_dates:
            try:
                values, payload = retrieve(current)
                stream.update(payload)
                records.append({"date": key, **values, "source_station": STATION})
            except Exception as exc:
                records.append({"date": key, "pm25": None, "pm10": None, "no2": None, "source_station": STATION, "error": str(exc)})
            pd.DataFrame(records).to_csv(output, index=False)
            time.sleep(0.35)
        current += timedelta(days=1)
    frame = pd.DataFrame(records).sort_values("date")
    frame.to_csv(output, index=False)
    manifest = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "source_url": URL, "station": STATION, "calendar_days": len(frame), "coverage_days": {column: int(frame[column].notna().sum()) for column in ["pm25", "pm10", "no2"]}, "new_response_stream_sha256": stream.hexdigest(), "role": "Historical recovery after AERIS/OpenAQ/S3 returned no observations for the requested 2012-15 period."}
    (DERIVED / "cetesb_recovery_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

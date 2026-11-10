#!/usr/bin/env python3
"""Retrieve the daily CETESB record for the AERIS-selected Taubate monitor."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
URL = "https://sistemasinter.cetesb.sp.gov.br/Ar/php/ar_dados_horarios_resultado.php"
STATION = "58/Taubaté"
START = date(2020, 4, 1)
END = date(2021, 3, 31)


def number(cell) -> float | None:
    text = " ".join(cell.stripped_strings).replace(",", ".").strip()
    if not text or text == "--":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def values_for_table(table) -> list[list[float | None]]:
    rows = []
    for row in table.find_all("tr"):
        cells = row.find_all("td", recursive=False)
        values = [number(cell) for cell in cells]
        if values and any(value is not None for value in values):
            rows.append(values)
    return rows


def parse_daily(html: bytes) -> dict[str, float | None]:
    parsed: dict[str, float | None] = {"pm25_ug_m3": None, "no2_ug_m3": None, "o3_ug_m3": None}
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        heading = " ".join(table.find_all("strong")[0].stripped_strings).upper() if table.find_all("strong") else ""
        values = values_for_table(table)
        if heading == "MP2.5":
            # CETESB's second column is the 24-hour mean. Its final reported value
            # is the end-of-day daily exposure record.
            daily = [row[1] for row in values if len(row) > 1 and row[1] is not None]
            parsed["pm25_ug_m3"] = daily[-1] if daily else None
        elif heading == "NO2":
            hourly = [row[0] for row in values if row[0] is not None]
            parsed["no2_ug_m3"] = sum(hourly) / len(hourly) if hourly else None
        elif heading == "O3":
            rolling = [row[1] for row in values if len(row) > 1 and row[1] is not None]
            parsed["o3_ug_m3"] = max(rolling) if rolling else None
    return parsed


def fetch(session: requests.Session, day: date) -> bytes:
    response = session.post(
        URL,
        data={"texData": day.strftime("%d/%m/%Y"), "selEst": STATION},
        timeout=(15, 30),
    )
    response.raise_for_status()
    return response.content


def main() -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    output = DERIVED / "cetesb_daily.csv"
    calendar = pd.date_range(START, END, freq="D")
    if output.exists():
        frame = pd.read_csv(output)
        frame["date"] = frame["date"].astype(str)
    else:
        frame = pd.DataFrame({"date": calendar.strftime("%Y-%m-%d")})
        for column in ("pm25_ug_m3", "no2_ug_m3", "o3_ug_m3", "error"):
            frame[column] = None
    digest = hashlib.sha256()
    session = requests.Session()
    session.headers.update({"User-Agent": "AERIS-reproduction/1.0"})
    for index, day in enumerate(calendar):
        row = frame.loc[frame["date"] == day.strftime("%Y-%m-%d")].iloc[0]
        if pd.notna(row["pm25_ug_m3"]) and pd.notna(row["no2_ug_m3"]) and pd.notna(row["o3_ug_m3"]):
            continue
        for attempt in range(3):
            try:
                payload = fetch(session, day.date())
                digest.update(payload)
                values = parse_daily(payload)
                for column, value in values.items():
                    frame.loc[frame["date"] == day.strftime("%Y-%m-%d"), column] = value
                frame.loc[frame["date"] == day.strftime("%Y-%m-%d"), "error"] = None
                break
            except requests.RequestException as exc:
                frame.loc[frame["date"] == day.strftime("%Y-%m-%d"), "error"] = str(exc)
                time.sleep(2**attempt)
        # Persist every response: a transient server failure never discards a
        # successfully recovered historical record.
        frame.to_csv(output, index=False)
        if index < len(calendar) - 1:
            time.sleep(1)
    frame.to_csv(output, index=False)
    summary = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": URL,
        "station": STATION,
        "date_range": [START.isoformat(), END.isoformat()],
        "daily_coverage": {column: int(frame[column].notna().sum()) for column in ("pm25_ug_m3", "no2_ug_m3", "o3_ug_m3")},
        "response_stream_sha256": digest.hexdigest(),
        "output": str(output),
    }
    (DERIVED / "cetesb_download.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

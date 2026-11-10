#!/usr/bin/env python3
"""Recover daily PM2.5 from CETESB for an AERIS-selected São Paulo station.

OpenAQ metadata identifies this station as a 2017--2023 PM2.5 source inside
the municipality, but its public historical payload lacks 2019 observations.
CETESB exposes those values through its no-auth historical station form.
"""

from __future__ import annotations

import argparse
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
DEFAULT_STATION = "31/Cid.Universitária-USP-Ipen"


def get_pm25_daily_mean(html: bytes) -> float | None:
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        rows = table.find_all("tr", recursive=False)
        if not rows:
            continue
        first = " ".join(rows[0].stripped_strings).upper()
        if not first.startswith("MP2.5"):
            continue
        values: list[float] = []
        for row in rows[2:]:
            cells = [" ".join(cell.stripped_strings) for cell in row.find_all("td", recursive=False)]
            if len(cells) < 2 or cells[1] == "--":
                continue
            try:
                values.append(float(cells[1].replace(",", ".")))
            except ValueError:
                continue
        if values:
            # CETESB reports a rolling 24-hour mean beside each hourly value.
            # The final non-missing value is the daily record available at day end.
            return values[-1]
    return None


def retrieve_day(day: date, station: str) -> tuple[float | None, bytes]:
    body = urllib.parse.urlencode(
        {"texData": day.strftime("%d/%m/%Y"), "selEst": station}
    ).encode()
    request = urllib.request.Request(URL, data=body, headers={"User-Agent": "AERIS-reproduction/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
    return get_pm25_daily_mean(payload), payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2019)
    parser.add_argument("--station", default=DEFAULT_STATION)
    parser.add_argument("--pause-seconds", type=float, default=1.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    DERIVED.mkdir(parents=True, exist_ok=True)
    output = DERIVED / "cetesb_pm25_daily.csv"
    manifest_path = DERIVED / "cetesb_pm25_download.json"
    if output.exists() and not args.force:
        print(f"Using existing {output}")
        return 0

    start = date(args.year, 1, 1)
    end = date(args.year, 12, 31)
    records: list[dict[str, object]] = []
    responses = hashlib.sha256()
    current = start
    while current <= end:
        try:
            value, payload = retrieve_day(current, args.station)
            responses.update(payload)
            records.append({"date": current.isoformat(), "mean": value, "source_station": args.station})
        except Exception as exc:  # Preserve an absent day as missing rather than inventing a value.
            records.append({"date": current.isoformat(), "mean": None, "source_station": args.station, "error": str(exc)})
        if current < end:
            time.sleep(args.pause_seconds)
        current += timedelta(days=1)

    frame = pd.DataFrame(records)
    frame.to_csv(output, index=False)
    manifest = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": URL,
        "request_parameters": {"station": args.station, "year": args.year},
        "n_calendar_days": len(frame),
        "n_pm25_days": int(frame["mean"].notna().sum()),
        "response_stream_sha256": responses.hexdigest(),
        "output": str(output),
        "role": (
            "Historical recovery for an AERIS-selected, inside-boundary station after the "
            "AERIS/OpenAQ run returned NO_OBSERVATIONS for 2019."
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

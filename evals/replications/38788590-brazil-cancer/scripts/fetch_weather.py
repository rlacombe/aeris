#!/usr/bin/env python3
"""Fetch a documented no-auth daily weather substitute for the published ERA5 covariates."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
PARAMS = {
    "latitude": "-23.5505",
    "longitude": "-46.6333",
    "start_date": "2019-01-01",
    "end_date": "2019-12-31",
    "daily": "temperature_2m_mean,relative_humidity_2m_mean",
    "timezone": "America/Sao_Paulo",
}


def main() -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    url = f"{BASE_URL}?{urllib.parse.urlencode(PARAMS)}"
    request = urllib.request.Request(url, headers={"User-Agent": "AERIS-reproduction/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        response_payload = json.loads(response.read())
    daily = response_payload.get("daily", {})
    frame = pd.DataFrame(
        {
            "date": daily.get("time", []),
            "temperature_c": daily.get("temperature_2m_mean", []),
            "relative_humidity_pct": daily.get("relative_humidity_2m_mean", []),
        }
    )
    if len(frame) != 365 or frame[["temperature_c", "relative_humidity_pct"]].isna().any().any():
        raise RuntimeError(f"Unexpected Open-Meteo response coverage: {len(frame)} daily rows")
    output = DERIVED / "weather_daily_open_meteo.csv"
    frame.to_csv(output, index=False)
    manifest = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": url,
        "output": str(output),
        "n_days": len(frame),
        "departure_from_paper": (
            "The paper used population-weighted ERA5 0.25-degree daily temperature and RH. "
            "This run uses a no-auth municipal-centroid Open-Meteo series."
        ),
    }
    (DERIVED / "weather_download.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

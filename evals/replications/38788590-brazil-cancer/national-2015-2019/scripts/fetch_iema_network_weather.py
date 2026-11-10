#!/usr/bin/env python3
"""Build national weather from capitals of states contributing IEMA PM2.5."""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
CAPITALS = {"BA": (-12.9714, -38.5014), "CE": (-3.7319, -38.5267), "DF": (-15.7939, -47.8828), "ES": (-20.3155, -40.3128), "GO": (-16.6869, -49.2648), "MG": (-19.9167, -43.9345), "PR": (-25.4284, -49.2733), "PE": (-8.0476, -34.8770), "RJ": (-22.9068, -43.1729), "RS": (-30.0346, -51.2177), "SP": (-23.5505, -46.6333)}
BASE = "https://archive-api.open-meteo.com/v1/archive"


def main() -> int:
    exposure = pd.read_csv(DERIVED / "iema_pm25_station_daily.csv")
    states = sorted(set(exposure.uf) & set(CAPITALS))
    frames, calls = [], []
    for uf in states:
        latitude, longitude = CAPITALS[uf]
        params = {"latitude": latitude, "longitude": longitude, "start_date": "2015-01-01", "end_date": "2019-12-31", "daily": "temperature_2m_mean,relative_humidity_2m_mean", "timezone": "UTC"}
        url = f"{BASE}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": "AERIS-reproduction/1.0"})
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = response.read()
        daily = json.loads(payload).get("daily", {})
        frame = pd.DataFrame({"date": daily.get("time", []), "temperature_c": daily.get("temperature_2m_mean", []), "relative_humidity_pct": daily.get("relative_humidity_2m_mean", [])})
        if len(frame) != 1826:
            raise RuntimeError(f"Unexpected weather coverage for {uf}: {len(frame)}")
        frame["uf"] = uf
        frames.append(frame)
        calls.append({"uf": uf, "latitude": latitude, "longitude": longitude, "url": url, "sha256": hashlib.sha256(payload).hexdigest()})
        time.sleep(0.25)
    output = pd.concat(frames).groupby("date", as_index=False)[["temperature_c", "relative_humidity_pct"]].mean()
    output.to_csv(DERIVED / "iema_network_weather_daily.csv", index=False)
    manifest = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "states": states, "aggregation": "Unweighted daily mean across capitals of states with retained IEMA PM2.5 stations.", "calls": calls}
    (DERIVED / "iema_network_weather_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"states": states, "days": len(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

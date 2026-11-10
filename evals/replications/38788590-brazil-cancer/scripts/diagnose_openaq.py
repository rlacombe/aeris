#!/usr/bin/env python3
"""Check whether OpenAQ sensor-day data exist behind a failed AERIS boundary run."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path) -> None:
    for line in path.read_text().splitlines() if path.exists() else []:
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> int:
    aeris_repo = Path(os.environ.get("AERIS_REPO", "."))
    load_dotenv(aeris_repo / ".env")
    sys.path.insert(0, str(aeris_repo))
    from aeris.exposure.api_clients import RateLimitedOpenAQ
    from aeris.exposure.config import Config

    config = Config.from_env()
    client = RateLimitedOpenAQ(config.openaq_api_key, config)
    candidates = json.loads((ROOT / "data" / "derived" / "aeris_pm25_candidate_stations.json").read_text())
    if not candidates:
        raise RuntimeError("No candidate station mapping. Run run_aeris_exposure.py first.")
    sensor_id = int(candidates[0]["sensor_id"])
    metadata = client._request(client.client._get, f"/sensors/{sensor_id}")
    daily = client._request(
        client.client._get,
        f"/sensors/{sensor_id}/days",
        params={
            "datetime_from": "2019-01-01T00:00:00Z",
            "datetime_to": "2019-12-31T23:59:59Z",
            "page": 1,
            "limit": 1000,
        },
    )
    metadata_payload = metadata.json()
    daily_payload = daily.json()
    result = {
        "queried_at_utc": datetime.now(timezone.utc).isoformat(),
        "sensor_id": sensor_id,
        "request_parameters": {
            "datetime_from": "2019-01-01T00:00:00Z",
            "datetime_to": "2019-12-31T23:59:59Z",
        },
        "sensor": metadata_payload.get("results", [{}])[0],
        "meta": daily_payload.get("meta"),
        "n_daily_rows": len(daily_payload.get("results", [])),
        "daily_sample": daily_payload.get("results", [])[:3],
        "interpretation": (
            "This diagnostic uses OpenAQ's documented datetime_from/datetime_to parameters. "
            "It is not substituted into the AERIS result; it tests whether a no-observations "
            "outcome reflects coverage or a retrieval-path issue."
        ),
    }
    output = ROOT / "data" / "derived" / "openaq_diagnostic_5233.json"
    output.write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

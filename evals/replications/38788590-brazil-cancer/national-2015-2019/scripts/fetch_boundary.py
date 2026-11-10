#!/usr/bin/env python3
"""Download the documented Brazil boundary used in the AERIS request."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
URL = "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/BRA/ADM0/geoBoundaries-BRA-ADM0_simplified.geojson"


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(URL, headers={"User-Agent": "AERIS-reproduction/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = response.read()
    geometry = json.loads(payload)
    if geometry.get("type") not in {"Feature", "FeatureCollection"}:
        raise RuntimeError("GeoBoundaries response is not GeoJSON.")
    output = RAW / "brazil_adm0.geojson"
    output.write_bytes(payload)
    record = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "url": URL,
              "output": str(output), "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    (RAW / "boundary_manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

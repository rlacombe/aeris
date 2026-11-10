#!/usr/bin/env python3
"""Fetch the public IBGE GeoJSON boundary for Sao Paulo municipality."""

from __future__ import annotations

import hashlib
import gzip
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
URL = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/3550308?"
    "formato=application/vnd.geo+json&qualidade=minima"
)


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    destination = RAW / "sao_paulo_3550308.geojson"
    request = urllib.request.Request(URL, headers={"User-Agent": "AERIS-reproduction/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
        if response.headers.get("Content-Encoding", "").lower() == "gzip" or payload[:2] == b"\x1f\x8b":
            payload = gzip.decompress(payload)
    parsed = json.loads(payload)
    if parsed.get("type") not in {"Feature", "FeatureCollection"}:
        raise RuntimeError("IBGE did not return GeoJSON feature data.")
    destination.write_bytes(payload)
    manifest = {
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": URL,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "output": str(destination),
    }
    (RAW / "boundary_download.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

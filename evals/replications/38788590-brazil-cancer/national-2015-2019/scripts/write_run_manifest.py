#!/usr/bin/env python3
"""Write a compact, checksummed manifest for the completed national run."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record(path: Path) -> dict[str, object]:
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": checksum(path)}


def main() -> int:
    inputs = [
        ROOT / "data" / "raw" / "sim" / "download_manifest.json",
        ROOT / "data" / "raw" / "iema" / "iema_download_manifest.json",
        ROOT / "data" / "raw" / "boundary_manifest.json",
        ROOT / "data" / "derived" / "aeris_national_tool_trace.json",
        ROOT / "data" / "derived" / "iema_pm25_ingestion_summary.json",
        ROOT / "data" / "derived" / "iema_network_weather_manifest.json",
        ROOT / "data" / "derived" / "sim_ingestion_summary.json",
    ]
    outputs = [
        ROOT / "data" / "derived" / "sim_national_daily_cancer_deaths.csv",
        ROOT / "data" / "derived" / "iema_pm25_national_daily.csv",
        ROOT / "data" / "derived" / "iema_network_weather_daily.csv",
        ROOT / "data" / "derived" / "national_analysis_panel_iema.csv",
        ROOT / "outputs" / "effect_result_iema.json",
        ROOT / "RESULT.md",
    ]
    result = json.loads((ROOT / "outputs" / "effect_result_iema.json").read_text())
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "study": {"pmid": "38788590", "window": "2015-01-01 through 2019-12-31", "scope": "Brazil national daily cancer mortality"},
        "direct_aeris_openaq_audit": {"days": 100, "study_days": 1826, "status": "insufficient for fit"},
        "fitted_source_record": {"pm25": "IEMA public state-monitor recovery", "weather": "Open-Meteo state-capital mean", "states_with_pm25": ["CE", "ES", "MG", "RJ", "SP"]},
        "result": result,
        "input_manifests": [record(path) for path in inputs],
        "outputs": [record(path) for path in outputs],
    }
    output = ROOT / "run_manifest.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"output": str(output), "result": result["effect"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

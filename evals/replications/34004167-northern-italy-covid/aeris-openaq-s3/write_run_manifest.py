"""Write checksums for the Northern Italy NO2 reconstruction artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


RUN_DIRECTORY = Path(__file__).resolve().parent
ARTIFACTS = (
    "article.xml",
    "dpc-covid19-ita-regioni.csv",
    "geoboundaries_ita_adm2.json",
    "geoboundaries_ita_adm2_simplified.geojson",
    "run_aeris_no2_overlap.py",
    "build_no2_overlap_panel.py",
    "fit_no2_overlap_gee.py",
    "aeris_no2_overlap_tool_trace.json",
    "aeris_no2_overlap_provenance.json",
    "aeris_no2_overlap_daily.csv",
    "aeris_no2_overlap_stations.csv",
    "no2_overlap_panel.csv",
    "no2_overlap_panel_manifest.json",
    "no2_overlap_model_results.json",
)


def checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    missing = [name for name in ARTIFACTS if not (RUN_DIRECTORY / name).exists()]
    if missing:
        raise RuntimeError(f"Missing required artifacts: {missing}")
    manifest = {
        "study": "PMID 34004167",
        "run": "AERIS/OpenAQ historical NO2 overlap reconstruction",
        "artifacts": {name: checksum(RUN_DIRECTORY / name) for name in ARTIFACTS},
    }
    (RUN_DIRECTORY / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"artifacts": len(ARTIFACTS)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

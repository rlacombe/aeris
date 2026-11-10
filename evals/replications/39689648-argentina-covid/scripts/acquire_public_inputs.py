"""Acquire the public inputs for PMID 39689648.

The official Argentina Ministry of Health archive is a 437 MB ZIP.  The script
does not fetch it again when the recorded file is already present.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
import argparse
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "manifests" / "public_inputs.json"
SOURCES = {
    "official_covid_cases": "https://sisa.msal.gov.ar/datos/descargas/covid-19/files/Covid19Casos.zip",
    "official_covid_catalog": "https://datos.salud.gob.ar/dataset/covid-19-casos-registrados-en-la-republica-argentina",
    "department_boundaries": "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/ARG/ADM2/geoBoundaries-ARG-ADM2_simplified.geojson",
    "department_boundary_metadata": "https://www.geoboundaries.org/api/current/gbOpen/ARG/ADM2/",
    "population_surface_2020": "https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/2020/ARG/arg_ppp_2020_1km_Aggregated_UNadj.tif",
}
FILES = {
    "official_covid_cases": RAW / "Covid19Casos.zip",
    "department_boundaries": RAW / "argentina_adm2.geojson",
    "department_boundary_metadata": RAW / "geoboundaries_adm2_metadata.json",
    "population_surface_2020": RAW / "arg_ppp_2020_1km_Aggregated_UNadj.tif",
}


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size:
        return
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "AERIS-reproduction/1.0"})
    with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    temporary.replace(destination)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-population",
        action="store_true",
        help="Download the public 2020 WorldPop surface required for department rates.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    # The population surface is optional for a correlation-only run. It is
    # requested separately because it is substantially larger than metadata.
    for source in ("official_covid_cases", "department_boundaries", "department_boundary_metadata"):
        download(SOURCES[source], FILES[source])
    if args.include_population:
        download(SOURCES["population_surface_2020"], FILES["population_surface_2020"])
    manifest = {
        "study": "PMID 39689648",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "sources": {
            name: {
                "url": SOURCES[name],
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": checksum(path),
            }
            for name, path in FILES.items()
            if path.exists()
        },
    }
    if not FILES["population_surface_2020"].exists():
        manifest["unfetched_optional_source"] = SOURCES["population_surface_2020"]
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

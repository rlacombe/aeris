"""Download pinned public inputs for the France COVID-19 reproduction."""

from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOUNDARY_URL = (
    "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/"
    "FRA/ADM2/geoBoundaries-FRA-ADM2_simplified.geojson"
)
OUTCOME_URL = "https://www.data.gouv.fr/fr/datasets/r/63352e38-d353-4b54-bfd1-f1b3ee1cabd7"
MENDLEY_WORKBOOK_URL = (
    "https://data.mendeley.com/public-files/datasets/2ghxnrkr9p/files/"
    "94c67954-cbf0-4e03-b109-6de6ab9d17cb/file_downloaded"
)
DEPARTMENT_CROSSWALK_URL = "https://geo.api.gouv.fr/departements?fields=nom,code&format=json"


def download(url: str, destination: Path) -> None:
    if destination.exists():
        return
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        destination.write_bytes(response.read())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    boundary_path = ROOT / "france_departments.geojson"
    download(BOUNDARY_URL, boundary_path)
    outcome_path = ROOT / "france_hospital_covid_all_departments.csv"
    covariate_path = ROOT / "authors_public_covariates.xlsx"
    department_crosswalk_path = ROOT / "france_department_codes.json"
    download(OUTCOME_URL, outcome_path)
    download(MENDLEY_WORKBOOK_URL, covariate_path)
    download(DEPARTMENT_CROSSWALK_URL, department_crosswalk_path)
    manifest = {
        "study": "PMID 34488764",
        "boundaries": {
            "url": BOUNDARY_URL,
            "geoBoundaries_release_commit": "9469f09",
            "boundary_id": "FRA-ADM2-29444166",
            "year_represented": 2022,
            "features": 96,
            "sha256": digest(boundary_path),
        },
        "outcome": {
            "source_file": str(outcome_path),
            "source_url": OUTCOME_URL,
            "sha256": digest(outcome_path),
        },
        "covariates": {
            "source_url": MENDLEY_WORKBOOK_URL,
            "dataset_doi": "10.17632/2ghxnrkr9p.4",
            "source_file": str(covariate_path),
            "sha256": digest(covariate_path),
        },
        "department_crosswalk": {
            "source_url": DEPARTMENT_CROSSWALK_URL,
            "source_file": str(department_crosswalk_path),
            "sha256": digest(department_crosswalk_path),
        },
    }
    (ROOT / "input_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()

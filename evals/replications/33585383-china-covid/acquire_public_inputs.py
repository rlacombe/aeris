"""Acquire the PMID 33585383 public analysis table and remove exposure fields."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from urllib.request import urlopen

import pandas as pd


RUN_DIRECTORY = Path(__file__).resolve().parent
SOURCE_URL = (
    "https://raw.githubusercontent.com/DavideFornacca/COVID19/master/China/"
    "covid_air_china_s5_20200523.csv"
)
EXPECTED_SHA256 = "9f53ecac262d37d3770fbfadca16ec7a79af3b98148b53b22f96c23ff85b976c"
OUTCOME_COLUMNS = [
    "province", "prefecture", "pop", "pop_dens", "cases", "cases_100k",
    "deaths", "deaths_100k", "mortality",
]


def main() -> int:
    target = RUN_DIRECTORY / "public_inputs"
    target.mkdir(exist_ok=True)
    raw_path = target / "covid_air_china_s5_20200523.csv"
    raw_path.write_bytes(urlopen(SOURCE_URL, timeout=60).read())
    digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"Unexpected source hash: {digest}")

    raw = pd.read_csv(raw_path)
    outcomes = raw.loc[:, OUTCOME_COLUMNS].copy()
    outcomes.insert(0, "subject_id", outcomes.index.astype(str))
    outcomes.to_csv(target / "outcomes_without_author_exposure.csv", index=False)
    manifest = {
        "pmid": "33585383",
        "accessed": date.today().isoformat(),
        "source_url": SOURCE_URL,
        "raw_file": raw_path.name,
        "raw_sha256": digest,
        "raw_rows": len(raw),
        "model_input_file": "outcomes_without_author_exposure.csv",
        "model_input_columns": [str(column) for column in outcomes.columns],
        "excluded_author_exposure_columns": [
            str(column) for column in raw.columns if column not in OUTCOME_COLUMNS
        ],
    }
    (target / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

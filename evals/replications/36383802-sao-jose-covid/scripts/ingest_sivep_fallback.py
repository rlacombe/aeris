#!/usr/bin/env python3
"""Build a public SIVEP-Gripe daily hospital-admission fallback series."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyreadr


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"
START, END = "2020-04-01", "2021-04-30"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    source = RAW / "sivep_hospital_2022.rds"
    if not source.exists():
        raise FileNotFoundError(source)
    DERIVED.mkdir(parents=True, exist_ok=True)
    frame = pyreadr.read_r(source)[None]
    frame["admission_date"] = pd.to_datetime(frame["DateAdmission"], errors="coerce")
    selected = frame[
        (frame["Municip_resid"] == "SAO JOSE DOS CAMPOS")
        & (frame["Admission"] == True)  # noqa: E712
        & (frame["SRAG"] == "COVID")
        & frame["admission_date"].between(START, END)
    ].copy()
    days = pd.date_range(START, END, freq="D")
    output = pd.DataFrame({"date": days.strftime("%Y-%m-%d")})
    output["covid_admissions"] = output["date"].map(selected.groupby(selected.admission_date.dt.strftime("%Y-%m-%d")).size()).fillna(0).astype(int)
    output["in_hospital_deaths"] = output["date"].map(selected.loc[selected.Outcome == "Death_Covid"].groupby(selected.loc[selected.Outcome == "Death_Covid", "admission_date"].dt.strftime("%Y-%m-%d")).size()).fillna(0).astype(int)
    destination = DERIVED / "sivep_daily_covid_admissions.csv"
    output.to_csv(destination, index=False)
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "CADDE-CENTRE/covid19_brazil_hfr processed public SIVEP-Gripe archive",
        "source_url": "https://raw.githubusercontent.com/CADDE-CENTRE/covid19_brazil_hfr/main/inst/data/SIVEP_hospital_31-01-2022-all.rds",
        "source_sha256": sha256(source),
        "selection": "Municip_resid=SAO JOSE DOS CAMPOS; Admission=True; SRAG=COVID; DateAdmission within study window.",
        "observation_window": [START, END],
        "admissions": int(output.covid_admissions.sum()),
        "deaths": int(output.in_hospital_deaths.sum()),
        "days": len(output),
        "departure_from_paper": "The paper used SIH/SUS B34.2 admissions. This public fallback is the SIVEP-Gripe severe-respiratory-hospitalization series and includes public and private hospitals.",
        "output": str(destination),
    }
    (DERIVED / "sivep_fallback_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

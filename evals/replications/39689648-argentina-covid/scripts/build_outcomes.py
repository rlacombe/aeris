"""Aggregate the Ministry of Health line list to the paper's study window."""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT / "data" / "raw" / "Covid19Casos.zip"
OUTPUT = ROOT / "data" / "derived" / "department_covid_outcomes_2020.csv"
MANIFEST = ROOT / "manifests" / "outcome_aggregation.json"
START = pd.Timestamp("2020-03-01")
END = pd.Timestamp("2021-01-01")
COLUMNS = [
    "residencia_provincia_id",
    "residencia_provincia_nombre",
    "residencia_departamento_id",
    "residencia_departamento_nombre",
    "fecha_diagnostico",
    "cuidado_intensivo",
    "fallecido",
    "clasificacion_resumen",
]


def is_confirmed(series: pd.Series) -> pd.Series:
    return series.fillna("").str.casefold().str.contains("confirmado", regex=False)


def main() -> None:
    accumulators: list[pd.DataFrame] = []
    rows_seen = 0
    rows_window = 0
    with zipfile.ZipFile(ZIP_PATH) as archive, archive.open("Covid19Casos.csv") as source:
        for chunk in pd.read_csv(source, usecols=COLUMNS, chunksize=200_000, low_memory=False):
            rows_seen += len(chunk)
            chunk["fecha_diagnostico"] = pd.to_datetime(chunk["fecha_diagnostico"], errors="coerce")
            chunk = chunk.loc[
                chunk["fecha_diagnostico"].ge(START)
                & chunk["fecha_diagnostico"].lt(END)
                & chunk["residencia_provincia_id"].notna()
                & chunk["residencia_departamento_id"].notna()
                & is_confirmed(chunk["clasificacion_resumen"])
            ].copy()
            rows_window += len(chunk)
            if chunk.empty:
                continue
            chunk["icu_admission"] = chunk["cuidado_intensivo"].eq("SI")
            chunk["death"] = chunk["fallecido"].eq("SI")
            accumulators.append(
                chunk.groupby(
                    [
                        "residencia_provincia_id",
                        "residencia_provincia_nombre",
                        "residencia_departamento_id",
                        "residencia_departamento_nombre",
                    ],
                    dropna=False,
                ).agg(
                    confirmed_cases=("fecha_diagnostico", "size"),
                    icu_admissions=("icu_admission", "sum"),
                    deaths=("death", "sum"),
                )
            )
    if not accumulators:
        raise RuntimeError("No confirmed case records in the requested study window.")
    outcomes = pd.concat(accumulators).groupby(level=list(range(4))).sum().reset_index()
    outcomes["department_code"] = (
        outcomes["residencia_provincia_id"].astype(int).astype(str).str.zfill(2)
        + outcomes["residencia_departamento_id"].astype(int).astype(str).str.zfill(3)
    )
    outcomes = outcomes.sort_values("department_code")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    outcomes.to_csv(OUTPUT, index=False)
    MANIFEST.write_text(
        json.dumps(
            {
                "study": "PMID 39689648",
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "source": "Argentina Ministry of Health Covid19Casos.zip",
                "date_window": {"start_inclusive": str(START.date()), "end_exclusive": str(END.date())},
                "case_definition": "clasificacion_resumen contains Confirmado",
                "department_count": int(len(outcomes)),
                "confirmed_case_records": int(outcomes["confirmed_cases"].sum()),
                "rows_seen": rows_seen,
                "rows_included": rows_window,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

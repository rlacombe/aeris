"""Fit the published department-level PM2.5 outcome correlations."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RATES = ROOT / "data" / "derived" / "department_covid_rates_2020.csv"
EXPOSURE = ROOT / "outputs" / "aeris_department_pm25_2020.csv"
PANEL = ROOT / "outputs" / "analytic_panel.csv"
RESULT = ROOT / "outputs" / "effect_results.json"

PUBLISHED = {
    "confirmed_cases_per_100k": -0.09,
    "icu_admissions_per_100k": -0.16,
    "deaths_per_100k": -0.11,
}


def main() -> None:
    rates = pd.read_csv(RATES, dtype={"department_code": str})
    exposure = pd.read_csv(EXPOSURE, dtype={"department_code": str})
    panel = rates.merge(
        exposure.loc[exposure["department_code"].notna()], on="department_code", how="inner"
    )
    panel = panel.loc[
        panel["population_density_per_km2"].ge(5)
        & panel["mean"].notna()
        & panel["qc_flag"].eq("PASS")
    ].copy()
    panel.to_csv(PANEL, index=False)
    if len(panel) < 3:
        raise RuntimeError(
            f"Only {len(panel)} departments satisfy the published density rule and have AERIS PM2.5."
        )
    results = {
        "study": "PMID 39689648",
        "design": "Pearson correlation across departments with density >=5 people/km2",
        "exposure": "AERIS/OpenAQ annual PM2.5 mean, 2020-03-01 through 2020-12-31",
        "analytic_departments": int(len(panel)),
        "published_analytic_districts": 332,
        "effects": [],
    }
    for outcome, published in PUBLISHED.items():
        results["effects"].append(
            {
                "outcome": outcome,
                "published_pearson_r": published,
                "aeris_pearson_r": float(panel["mean"].corr(panel[outcome], method="pearson")),
            }
        )
    RESULT.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

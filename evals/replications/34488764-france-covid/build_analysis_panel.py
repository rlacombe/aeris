"""Build the May 1, 2020 France department analysis panel before exposure merge."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
TARGET_DATE = pd.Timestamp("2020-05-01")


def normalized_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return "".join(character for character in value.casefold() if character.isalnum())


def main() -> None:
    outcomes = pd.read_csv(ROOT / "france_hospital_covid_all_departments.csv", sep=";")
    outcomes["jour"] = pd.to_datetime(outcomes["jour"])
    outcomes["dep"] = outcomes["dep"].astype(str).str.zfill(2)
    outcomes = outcomes.loc[
        (outcomes["jour"] == TARGET_DATE)
        & (outcomes["sexe"] == 0)
        & outcomes["dep"].str.fullmatch(r"(?:0[1-9]|[1-8][0-9]|9[0-5]|2A|2B)")
    ].copy()
    outcomes = outcomes[["dep", "dc"]].rename(columns={"dc": "covid_deaths"})

    crosswalk = pd.DataFrame(json.loads((ROOT / "france_department_codes.json").read_text()))
    crosswalk = crosswalk.rename(columns={"code": "dep", "nom": "department_name"})
    crosswalk["department_key"] = crosswalk["department_name"].map(normalized_name)
    outcomes = outcomes.merge(crosswalk, on="dep", how="inner", validate="one_to_one")

    covariates = pd.read_excel(ROOT / "authors_public_covariates.xlsx", sheet_name="Data")
    covariates = covariates.loc[
        (covariates["COUNTRY"] == "France") & covariates["NUTS3"].notna() & (covariates["NUTS3"] != "-")
    ].copy()
    covariates["department_key"] = covariates["NUTS3"].map(normalized_name)
    covariates = covariates.rename(
        columns={
            "NUTS3": "department_name_authors",
            "POPULATION": "population",
            "%POP>=60": "share_60_plus",
            "%FEMEALS": "share_female",
            "POP_DENS": "population_density",
            "Diabetes %": "diabetes_prevalence",
            "BEDS_Intcare/reanim": "intensive_care_beds",
            "Temp_mean_over12yrs": "mean_temperature",
        }
    )
    keep = [
        "department_key",
        "department_name_authors",
        "population",
        "share_60_plus",
        "share_female",
        "population_density",
        "diabetes_prevalence",
        "intensive_care_beds",
        "mean_temperature",
    ]
    covariates = covariates[keep]
    panel = outcomes.merge(covariates, on="department_key", how="inner", validate="one_to_one")
    panel["intensive_care_beds_per_100k"] = 100000 * panel["intensive_care_beds"] / panel["population"]
    panel.to_csv(ROOT / "analysis_panel_pre_exposure.csv", index=False)

    summary = {
        "target_date": TARGET_DATE.date().isoformat(),
        "mainland_outcome_departments": len(outcomes),
        "authors_covariate_departments": len(covariates),
        "matched_departments": len(panel),
        "unmatched_outcome_departments": sorted(set(outcomes["department_name"]) - set(panel["department_name"])),
        "unmatched_covariate_departments": sorted(
            set(covariates["department_name_authors"]) - set(panel["department_name_authors"])
        ),
    }
    (ROOT / "analysis_panel_summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()

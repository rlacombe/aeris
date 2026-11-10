"""Attempt the July 2020 public municipal PM2.5 model for PMID 34260961.

The attempt is deliberately made after, rather than before, checking exposure
variation.  An exposure coefficient cannot be estimated when every included
municipality has the same AERIS-derived PM2.5 value.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


RUN_DIRECTORY = Path(__file__).resolve().parent
TARGET_DATE = "2020-07-24"
PUBLISHED_STANDARDIZED_PM25_BETA = 0.403


def main() -> int:
    outcomes = pd.read_csv(
        RUN_DIRECTORY / "public_outcomes_four_peaks.csv", dtype={"city_code": str}
    )
    exposures = pd.read_csv(
        RUN_DIRECTORY / "aeris_pm25_study_period.csv", dtype={"subject_id": str}
    )
    panel = outcomes.loc[outcomes["date"] == TARGET_DATE].merge(
        exposures,
        left_on="city_code",
        right_on="subject_id",
        how="inner",
        validate="one_to_one",
    )
    panel.to_csv(RUN_DIRECTORY / "public_model_panel.csv", index=False)

    values = pd.to_numeric(panel["pm25_2016_2019_ug_m3"], errors="coerce").dropna()
    result = {
        "study_pmid": "34260961",
        "target_date": TARGET_DATE,
        "outcome": "log cumulative municipal COVID-19 case rate",
        "exposure": "AERIS OpenAQ PM2.5, annual S3-archive fallback, 2016-2019",
        "municipalities_in_public_outcome_table": int((outcomes["date"] == TARGET_DATE).sum()),
        "municipalities_with_aeris_exposure": int(values.size),
        "unique_aeris_pm25_values": int(values.nunique()),
        "aeris_pm25_sd": float(values.std(ddof=1)) if values.size > 1 else 0.0,
        "published_standardized_pm25_beta": PUBLISHED_STANDARDIZED_PM25_BETA,
        "effect_estimated": False,
        "reason": (
            "The reconstructed exposure has zero municipal variation: all included "
            "municipalities are assigned the same sole historical OpenAQ PM2.5 station. "
            "PM2.5 is therefore collinear with the intercept, before any public covariates "
            "are considered."
        ),
    }
    (RUN_DIRECTORY / "public_model_attempt.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

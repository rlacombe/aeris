"""Fit the published PM2.5--COVID mortality Kendall analysis using completed AERIS output."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from scipy.stats import kendalltau


RUN_DIRECTORY = Path(__file__).resolve().parent
YEARS = (2014, 2015, 2016)


def completed_annual_paths(year: int) -> list[Path]:
    """Return one completed annual export, or its completed cohort exports.

    A combined annual export is preferred because it already contains each
    successful cohort once. Early interrupted runs may only leave cohort files.
    """
    combined = RUN_DIRECTORY / f"aeris_pm25_{year}.csv"
    if combined.exists():
        return [combined]
    return sorted(RUN_DIRECTORY.glob(f"aeris_pm25_{year}_*.csv"))


def main() -> int:
    annual = []
    for year in YEARS:
        paths = completed_annual_paths(year)
        for path in paths:
            frame = pd.read_csv(path)
            frame = frame.loc[
                frame["mean"].notna(), ["subject_id", "mean", "n_samples", "unit"]
            ].copy()
            frame["year"] = year
            annual.append(frame)

    if not annual:
        raise FileNotFoundError("No completed AERIS PM2.5 exports were found.")

    exposure = pd.concat(annual, ignore_index=True)
    exposure["weighted_sum"] = exposure["mean"] * exposure["n_samples"]
    combined = (
        exposure.groupby("subject_id", as_index=False)
        .agg(
            weighted_sum=("weighted_sum", "sum"),
            observed_days=("n_samples", "sum"),
            years_with_data=("year", "nunique"),
            unit=("unit", "first"),
        )
    )
    combined["aeris_pm25_ug_m3"] = combined["weighted_sum"] / combined["observed_days"]
    combined = combined.drop(columns="weighted_sum")

    outcomes = pd.read_csv(RUN_DIRECTORY / "public_inputs" / "outcomes_without_author_exposure.csv")
    outcomes["subject_id"] = outcomes["subject_id"].astype(str)
    combined["subject_id"] = combined["subject_id"].astype(str)
    panel = outcomes.merge(combined, on="subject_id", how="inner", validate="one_to_one")
    panel = panel.loc[panel["mortality"].notna()].copy()
    panel.to_csv(RUN_DIRECTORY / "analysis_panel.csv", index=False)

    unique_exposures = int(panel["aeris_pm25_ug_m3"].nunique())
    result = kendalltau(panel["aeris_pm25_ug_m3"], panel["mortality"], variant="b")
    identifiable = len(panel) >= 3 and unique_exposures >= 2
    output = {
        "pmid": "33585383",
        "analysis": "Kendall tau-b: reconstructed 2014-2016 AERIS/OpenAQ PM2.5 vs COVID-19 mortality (%)",
        "n": int(len(panel)),
        "tau_b": float(result.statistic),
        "p_value": float(result.pvalue),
        "confidence_interval_95": None,
        "confidence_interval_status": (
            "not_estimable: the completed panel has fewer than three rows or no exposure variation"
            if not identifiable
            else "not_computed: Kendall tau confidence intervals were outside the published analysis"
        ),
        "n_unique_exposure_values": unique_exposures,
        "published_pm25_ground_tau_b": 0.18,
        "published_pm25_ground_n": 287,
        "exposure_unit": panel["unit"].dropna().iloc[0] if panel["unit"].notna().any() else None,
        "median_observed_days": float(panel["observed_days"].median()),
        "median_years_with_data": float(panel["years_with_data"].median()),
        "exposure_source": "AERIS OpenAQ v3 daily endpoint with AERIS public S3 archive fallback",
        "source_substitution": "The authors' PM25_gr field was excluded before analysis. The published field is AQI; AERIS reconstructs PM2.5 in ug/m3. Kendall tau is invariant to strictly monotonic unit changes, but the monitoring source and spatial assignment differ.",
    }
    (RUN_DIRECTORY / "model_result.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

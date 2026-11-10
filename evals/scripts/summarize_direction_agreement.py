#!/usr/bin/env python3
"""Summarize direction agreement across completed AERIS replications."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmark"
NEAR_NULL_RATIO_BOUND = 1.05


def direction(effect: float) -> int:
    log_effect = math.log(effect)
    return (log_effect > 0) - (log_effect < 0)


def is_near_null(effect: float) -> bool:
    """Return whether an effect is within 5% of the null ratio."""
    return 1 / NEAR_NULL_RATIO_BOUND <= effect <= NEAR_NULL_RATIO_BOUND


def agreement_category(published: float, aeris: float) -> str:
    published_near_null = is_near_null(published)
    aeris_near_null = is_near_null(aeris)
    if published_near_null and aeris_near_null:
        return "both_near_null"
    if published_near_null:
        return "published_near_null_aeris_non_null"
    if aeris_near_null:
        return "published_non_null_aeris_near_null"
    if direction(published) == direction(aeris):
        return "same_non_null_direction"
    return "opposite_non_null_direction"


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    comparable = [
        row for row in rows
        if direction(float(row["published_effect"])) != 0
        and direction(float(row["aeris_effect"])) != 0
    ]
    agreements = sum(
        direction(float(row["published_effect"])) == direction(float(row["aeris_effect"]))
        for row in comparable
    )
    categories: dict[str, int] = {}
    for row in comparable:
        category = agreement_category(float(row["published_effect"]), float(row["aeris_effect"]))
        row["agreement_category"] = category
        categories[category] = categories.get(category, 0) + 1
    return {
        "n_effects_with_reported_direction": len(comparable),
        "n_same_direction": agreements,
        "proportion_same_direction": agreements / len(comparable) if comparable else None,
        "agreement_categories": categories,
        "effects": comparable,
    }


def main() -> None:
    direct = pd.read_csv(BENCHMARK / "effect_comparisons.csv")
    rows = direct[["study_id", "study_label", "published_effect", "aeris_effect"]].to_dict("records")

    oecd = pd.read_csv(
        ROOT / "replications" / "33484722-oecd-covid" / "reproduction_model_results.csv"
    )
    oecd = oecd.loc[
        (oecd["exposure_coverage_rule"] == "sensitivity_65pct_annual_coverage")
        & (oecd["specification"] == "closest_complete_public_specification")
    ]
    for _, row in oecd.iterrows():
        rows.append(
            {
                "study_id": "33484722",
                "study_label": f"OECD COVID-19, day {int(row['event_day'])} {row['outcome']}",
                "published_effect": float(row["published_pm25_rate_ratio_per_ug_m3"]),
                "aeris_effect": float(row["aeris_pm25_rate_ratio_per_ug_m3"]),
            }
        )

    brazil = json.loads(
        (
            ROOT
            / "replications"
            / "38788590-brazil-cancer"
            / "outputs"
            / "effect_result_cetesb_recovery.json"
        ).read_text()
    )
    rows.append(
        {
            "study_id": "38788590",
            "study_label": "Brazil cancer mortality, Sao Paulo 2019 sensitivity",
            "published_effect": float(brazil["published_2015_2019_or_per_10"]),
            "aeris_effect": float(brazil["effect"]["odds_ratio_per_10_ug_m3"]),
        }
    )

    output = {
        "definition": "An effect agrees in direction when published and AERIS log effect ratios have the same sign.",
        "near_null_definition": "Effect ratio within 0.95 to 1.05 for the study's stated exposure increment.",
        "all_fitted_effect_pairs": summarize(rows),
        "three_direct_comparisons": summarize(rows[: len(direct)]),
        "excluded": [
            "Northern Italy: published effects are rounded to 1.00, so direction is unavailable.",
            "US stroke: the completed model uses a different outcome and has no published comparison effect.",
        ],
    }
    output_path = BENCHMARK / "direction_agreement.json"
    output_path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()

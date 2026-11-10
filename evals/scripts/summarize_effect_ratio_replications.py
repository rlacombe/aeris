#!/usr/bin/env python3
"""Summarize fitted reconstructions on a common multiplicative effect scale."""

import csv
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "benchmark"
CSV_PATH = BENCHMARK / "effect_ratio_comparisons.csv"
JSON_PATH = BENCHMARK / "effect_ratio_replication_metrics.json"
MATERIALITY_PATH = BENCHMARK / "materiality_agreement.csv"
MAGNITUDE_PATH = BENCHMARK / "effect_magnitude_agreement.csv"
STUDY_LEVEL_PATH = BENCHMARK / "study_level_meta_reproduction.csv"
MATERIAL_RATIO = 1.05
PRIMARY_EXCLUSIONS = {
    "Israel COVID-19": "No usable spatially varying PM2.5 exposure panel for the study dates."
}
CALIBRATION_EXCLUSIONS = {
    "Northern Italy COVID-19": "The published contrasts are reported only as RR 1.00."
}


# Each pair is an odds ratio, rate ratio, or ratio derived from the study's
# stated contrast. Values were transcribed from each replication's RESULT.md.
ROWS = [
    ("UK COVID-19", "OR per 10 ug/m3 PM2.5", 1.13, 1.4576, 1.09, 1.16, 1.2059, 1.7619),
    ("Italy COVID-19", "OR per doubling PM10 exceedance days", 1.7569, 1.7408, None, None, 1.1279, 2.6878),
    ("France COVID-19", "rate ratio per 1 ug/m3 PM2.5", 1.2440, 1.048509, 1.083, 1.428, 0.953344, 1.153174),
    ("OECD COVID-19", "rate ratio per 1 ug/m3 PM2.5, day 60 cases", 1.0202013, 0.9981993, None, None, 0.8532257, 1.1678056),
    ("OECD COVID-19", "rate ratio per 1 ug/m3 PM2.5, day 60 deaths", 1.0304545, 1.0156307, None, None, 0.8062486, 1.2793890),
    ("OECD COVID-19", "rate ratio per 1 ug/m3 PM2.5, day 80 cases", 1.0202013, 0.9709430, None, None, 0.9260276, 1.0180369),
    ("OECD COVID-19", "rate ratio per 1 ug/m3 PM2.5, day 80 deaths", 1.0090406, 0.9705941, None, None, 0.8726769, 1.0794980),
    ("Israel COVID-19", "rate ratio per 1 SD pollutant", math.exp(0.086), math.exp(-0.0015999171), None, None, math.exp(-0.1486669441), math.exp(0.1454671099)),
    ("Northern Italy COVID-19", "rate ratio per 1 ug/m3 NO2, incidence", 1.0, 1.05056, None, None, 1.04162, 1.05958),
    ("Northern Italy COVID-19", "rate ratio per 1 ug/m3 NO2, mortality", 1.0, 0.98813, None, None, 0.98662, 0.98964),
    ("Sao Jose COVID admissions", "rate ratio per 10 ug/m3 O3, lag 2", 1.061, 1.003, 1.016, 1.108, 0.981, 1.026),
    ("Sao Jose COVID admissions", "rate ratio per 10 ug/m3 NO2, lag 3", 1.125, 1.034, 1.050, 1.205, 0.876, 1.220),
    ("Sao Paulo AMI admissions", "rate ratio, high-pollution cluster", 1.09, 1.0688491129, None, None, 1.0061673232, 1.1351658487),
    ("Brazil cancer mortality", "OR per 10 ug/m3 PM2.5", 1.01, 1.060, 1.00, 1.02, 1.052, 1.069),
    # The article and reconstruction use linear mortality-rate models. Ratios
    # equal 1 + 10 * beta / the corresponding mean mortality rate: 143.50 and
    # 271.271739 deaths per 100,000, respectively.
    ("US stroke mortality", "rate ratio per 10 ug/m3 PM2.5", 1 + 10 * 1.89 / 143.50, 1 + 10 * 3.0055124997 / 271.27173913, None, None, 1 - 10 * 10.0967805913 / 271.27173913, 1 + 10 * 16.1078055907 / 271.27173913),
]


def pearson(x, y):
    x_bar = sum(x) / len(x)
    y_bar = sum(y) / len(y)
    numerator = sum((a - x_bar) * (b - y_bar) for a, b in zip(x, y))
    denominator = math.sqrt(sum((a - x_bar) ** 2 for a in x) * sum((b - y_bar) ** 2 for b in y))
    return numerator / denominator


def linear_fit(x, y):
    """Return intercept, slope, and residual R-squared for a least-squares fit."""
    x_bar = sum(x) / len(x)
    y_bar = sum(y) / len(y)
    denominator = sum((value - x_bar) ** 2 for value in x)
    slope = sum((a - x_bar) * (b - y_bar) for a, b in zip(x, y)) / denominator
    intercept = y_bar - slope * x_bar
    residual_sse = sum((b - (intercept + slope * a)) ** 2 for a, b in zip(x, y))
    total_sst = sum((b - y_bar) ** 2 for b in y)
    return intercept, slope, 1 - residual_sse / total_sst


def effect_status(low, high):
    if low is None or high is None:
        return None
    if low > 1:
        return "positive"
    if high < 1:
        return "negative"
    return "null"


def material_point_status(ratio):
    if ratio > MATERIAL_RATIO:
        return "positive_material"
    if ratio < 1 / MATERIAL_RATIO:
        return "negative_material"
    return "negligible"


def material_interval_status(low, high):
    if low is None or high is None:
        return None
    if low > MATERIAL_RATIO:
        return "positive_material"
    if high < 1 / MATERIAL_RATIO:
        return "negative_material"
    if low >= 1 / MATERIAL_RATIO and high <= MATERIAL_RATIO:
        return "negligible"
    return "indeterminate"


def geometric_mean(values):
    return math.exp(sum(math.log(value) for value in values) / len(values))


def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def rank(values):
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and ordered[end][1] == ordered[start][1]:
            end += 1
        average_rank = (start + 1 + end) / 2
        for index, _ in ordered[start:end]:
            ranks[index] = average_rank
        start = end
    return ranks


def main():
    BENCHMARK.mkdir(parents=True, exist_ok=True)
    primary_rows = [row for row in ROWS if row[0] not in PRIMARY_EXCLUSIONS]
    calibration_rows = [
        row for row in primary_rows if row[0] not in CALIBRATION_EXCLUSIONS
    ]
    study_groups = {}
    for row in calibration_rows:
        study_groups.setdefault(row[0], []).append(row)
    study_level_rows = []
    study_mean_absolute_log_errors = {}
    for study, rows in study_groups.items():
        published_ratio = geometric_mean([row[2] for row in rows])
        aeris_ratio = geometric_mean([row[3] for row in rows])
        study_level_rows.append((study, len(rows), published_ratio, aeris_ratio))
        study_mean_absolute_log_errors[study] = sum(
            abs(math.log(row[3] / row[2])) for row in rows
        ) / len(rows)
    with CSV_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["study", "effect_scale", "published_ratio", "aeris_ratio", "published_ci_low", "published_ci_high", "aeris_ci_low", "aeris_ci_high", "included_primary_meta", "primary_meta_exclusion"])
        for row in ROWS:
            writer.writerow([
                *row,
                str(row[0] not in PRIMARY_EXCLUSIONS).lower(),
                PRIMARY_EXCLUSIONS.get(row[0], ""),
            ])

    published = [row[2] for row in primary_rows]
    aeris = [row[3] for row in primary_rows]
    log_errors = [abs(math.log(a / p)) for p, a in zip(published, aeris)]
    ratios = [a / p for p, a in zip(published, aeris)]
    log_published = [math.log(value) for value in published]
    log_aeris = [math.log(value) for value in aeris]
    identity_sse = sum((a - p) ** 2 for p, a in zip(published, aeris))
    identity_sst = sum((p - sum(published) / len(published)) ** 2 for p in published)
    directional_pairs = [(p, a) for p, a in zip(published, aeris) if p != 1]
    sign_agreement = sum((p > 1) == (a > 1) for p, a in directional_pairs) / len(directional_pairs)
    ci_pairs = [row for row in primary_rows if row[4] is not None and row[6] is not None]
    ci_overlap = sum(max(row[4], row[6]) <= min(row[5], row[7]) for row in ci_pairs)
    published_point_in_aeris_interval = sum(
        row[6] <= row[2] <= row[7] for row in ci_pairs
    )
    aeris_point_in_published_interval = sum(
        row[4] <= row[3] <= row[5] for row in ci_pairs
    )
    status_pairs = [
        (effect_status(row[4], row[5]), effect_status(row[6], row[7]))
        for row in ci_pairs
    ]
    point_materiality_pairs = [
        (material_point_status(row[2]), material_point_status(row[3]))
        for row in primary_rows
    ]
    interval_materiality_pairs = [
        (material_interval_status(row[4], row[5]), material_interval_status(row[6], row[7]))
        for row in ci_pairs
    ]
    published_material_points = [pair for pair in point_materiality_pairs if pair[0] != "negligible"]
    published_negligible_points = [pair for pair in point_materiality_pairs if pair[0] == "negligible"]
    published_material_intervals = [
        pair for pair in interval_materiality_pairs
        if pair[0] in {"positive_material", "negative_material"}
    ]
    within_five_percent = [error <= math.log(1.05) for error in log_errors]
    within_ten_percent = [error <= math.log(1.10) for error in log_errors]
    material_indices = [
        index for index, row in enumerate(primary_rows)
        if material_point_status(row[2]) != "negligible"
    ]
    published_negligible_intervals = [
        pair for pair in interval_materiality_pairs if pair[0] == "negligible"
    ]
    published_effects = [pair for pair in status_pairs if pair[0] in {"positive", "negative"}]
    published_nulls = [pair for pair in status_pairs if pair[0] == "null"]
    intercept, slope, log_r_squared = linear_fit(log_published, log_aeris)
    leave_one_study_out_pearson = {}
    for study in sorted({row[0] for row in primary_rows}):
        kept = [row for row in primary_rows if row[0] != study]
        leave_one_study_out_pearson[study] = pearson(
            [row[2] for row in kept], [row[3] for row in kept]
        )
    study_published = [row[2] for row in study_level_rows]
    study_aeris = [row[3] for row in study_level_rows]
    study_log_errors = [
        study_mean_absolute_log_errors[study]
        for study, _, _, _ in study_level_rows
    ]
    material_study_rows = [
        row for row in study_level_rows if material_point_status(row[2]) != "negligible"
    ]
    near_null_study_rows = [
        row for row in study_level_rows if material_point_status(row[2]) == "negligible"
    ]

    metrics = {
        "effect_pairs": len(primary_rows),
        "primary_studies": len({row[0] for row in primary_rows}),
        "excluded_sensitivities": PRIMARY_EXCLUSIONS,
        "pearson_r": pearson(published, aeris),
        "spearman_rho": pearson(rank(published), rank(aeris)),
        "identity_r_squared": 1 - identity_sse / identity_sst,
        "mean_absolute_log_effect_error": sum(log_errors) / len(log_errors),
        "median_absolute_log_effect_error": median(log_errors),
        "geometric_mean_reconstructed_to_published_ratio": math.exp(sum(math.log(value) for value in ratios) / len(ratios)),
        "direction_agreement_excluding_published_null": sign_agreement,
        "direction_pairs_excluding_published_null": len(directional_pairs),
        "confidence_interval_overlap": ci_overlap,
        "confidence_interval_pairs": len(ci_pairs),
        "published_point_within_aeris_confidence_interval": published_point_in_aeris_interval,
        "aeris_point_within_published_confidence_interval": aeris_point_in_published_interval,
        "materiality_ratio_threshold": MATERIAL_RATIO,
        "within_5_percent_multiplicative_error": sum(within_five_percent),
        "within_10_percent_multiplicative_error": sum(within_ten_percent),
        "material_published_effects_within_10_percent_multiplicative_error": sum(
            within_ten_percent[index] for index in material_indices
        ),
        "material_published_effect_count": len(material_indices),
        "published_material_point_estimates": len(published_material_points),
        "published_material_point_estimates_reconstructed_same_direction": sum(
            (published == "positive_material" and aeris_ratio > 1)
            or (published == "negative_material" and aeris_ratio < 1)
            for (published, _), (_, aeris_ratio) in zip(
                published_material_points,
                [(material_point_status(row[2]), row[3]) for row in primary_rows
                 if material_point_status(row[2]) != "negligible"],
            )
        ),
        "published_negligible_point_estimates": len(published_negligible_points),
        "published_negligible_point_estimates_reconstructed_negligible": sum(
            aeris == "negligible" for _, aeris in published_negligible_points
        ),
        "published_material_effects_with_two_confidence_intervals": len(published_material_intervals),
        "published_material_effects_reconstructed_same_direction_with_two_confidence_intervals": sum(
            published == aeris for published, aeris in published_material_intervals
        ),
        "published_negligible_effects_with_two_confidence_intervals": len(published_negligible_intervals),
        "published_negligible_effects_reconstructed_negligible_with_two_confidence_intervals": sum(
            aeris == "negligible" for _, aeris in published_negligible_intervals
        ),
        "published_effects_with_two_confidence_intervals": len(published_effects),
        "published_effects_reconstructed_with_same_direction_effect": sum(
            published == aeris and published in {"positive", "negative"}
            for published, aeris in published_effects
        ),
        "published_nulls_with_two_confidence_intervals": len(published_nulls),
        "published_nulls_reconstructed_as_null": sum(
            aeris == "null" for _, aeris in published_nulls
        ),
        "log_scale_calibration_intercept": intercept,
        "log_scale_calibration_slope": slope,
        "log_scale_regression_r_squared": log_r_squared,
        "leave_one_study_out_pearson_r": leave_one_study_out_pearson,
        "leave_one_study_out_pearson_r_range": [
            min(leave_one_study_out_pearson.values()),
            max(leave_one_study_out_pearson.values()),
        ],
        "study_level_material_positive_studies": len(material_study_rows),
        "study_level_material_positive_same_direction": sum(
            (published_ratio > 1 and aeris_ratio > 1)
            or (published_ratio < 1 and aeris_ratio < 1)
            for _, _, published_ratio, aeris_ratio in material_study_rows
        ),
        "study_level_near_null_studies": len(near_null_study_rows),
        "study_level_near_null_retained": sum(
            material_point_status(aeris_ratio) == "negligible"
            for _, _, _, aeris_ratio in near_null_study_rows
        ),
        "study_level_pearson_r": pearson(study_published, study_aeris),
        "study_level_spearman_rho": pearson(rank(study_published), rank(study_aeris)),
        "study_level_median_absolute_log_effect_error": median(study_log_errors),
        "study_level_mean_absolute_log_effect_error": sum(study_log_errors) / len(study_log_errors),
        "study_level_geometric_mean_reconstructed_to_published_ratio": geometric_mean(
            [aeris_ratio / published_ratio for _, _, published_ratio, aeris_ratio in study_level_rows]
        ),
        "study_level_within_10_percent_multiplicative_error": sum(
            error <= math.log(1.10) for error in study_log_errors
        ),
    }
    JSON_PATH.write_text(json.dumps(metrics, indent=2) + "\n")
    with MATERIALITY_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "study", "effect_scale", "published_ratio", "aeris_ratio",
            "published_point_status", "aeris_point_status",
            "published_interval_status", "aeris_interval_status",
            "included_primary_meta",
        ])
        for row in ROWS:
            writer.writerow([
                row[0], row[1], row[2], row[3],
                material_point_status(row[2]), material_point_status(row[3]),
                material_interval_status(row[4], row[5]),
                material_interval_status(row[6], row[7]),
                row[0] not in PRIMARY_EXCLUSIONS,
            ])
    with MAGNITUDE_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "study", "effect_scale", "published_ratio", "aeris_ratio",
            "reconstructed_to_published_ratio", "absolute_log_error",
            "within_5_percent", "within_10_percent", "same_point_direction",
            "note", "included_primary_meta",
        ])
        for row in ROWS:
            published_ratio, aeris_ratio = row[2], row[3]
            error = abs(math.log(aeris_ratio / published_ratio))
            note = ""
            if row[0] == "Israel COVID-19":
                note = PRIMARY_EXCLUSIONS[row[0]]
            writer.writerow([
                row[0], row[1], published_ratio, aeris_ratio,
                aeris_ratio / published_ratio, error,
                error <= math.log(1.05), error <= math.log(1.10),
                "" if published_ratio == 1 else (published_ratio > 1) == (aeris_ratio > 1),
                note, row[0] not in PRIMARY_EXCLUSIONS,
            ])
    with STUDY_LEVEL_PATH.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "study", "contrasts_aggregated", "published_ratio", "aeris_ratio",
            "published_group", "aeris_group", "mean_absolute_log_error", "within_10_percent",
        ])
        for study, contrast_count, published_ratio, aeris_ratio in study_level_rows:
            mean_absolute_log_error = study_mean_absolute_log_errors[study]
            writer.writerow([
                study, contrast_count, published_ratio, aeris_ratio,
                material_point_status(published_ratio), material_point_status(aeris_ratio),
                mean_absolute_log_error,
                mean_absolute_log_error <= math.log(1.10),
            ])
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

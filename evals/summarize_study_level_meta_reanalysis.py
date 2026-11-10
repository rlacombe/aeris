#!/usr/bin/env python3
"""Summarize study-weighted calibration for AERIS source-substitution reanalyses."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd
from scipy.stats import pearsonr


def fisher_interval(r: float, n: int) -> tuple[float, float]:
    """Return the two-sided 95% Fisher-transformed interval for Pearson r."""
    if n <= 3 or abs(r) >= 1:
        return (float("nan"), float("nan"))
    z = math.atanh(r)
    margin = 1.96 / math.sqrt(n - 3)
    return (math.tanh(z - margin), math.tanh(z + margin))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    studies = pd.read_csv(args.input)
    published = studies["published_ratio"].to_numpy()
    aeris = studies["aeris_ratio"].to_numpy()
    r, p_value = pearsonr(published, aeris)
    ci_low, ci_high = fisher_interval(float(r), len(studies))
    result = {
        "n_studies": int(len(studies)),
        "pearson_r": float(r),
        "pearson_r_95_ci_fisher": [float(ci_low), float(ci_high)],
        "pearson_r_p_value": float(p_value),
        "median_absolute_log_effect_error": float(studies["mean_absolute_log_error"].median()),
        "mean_absolute_log_effect_error": float(studies["mean_absolute_log_error"].mean()),
        "within_10_percent": int(studies["within_10_percent"].sum()),
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

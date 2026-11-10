"""
Wearable Cardiac Biomarkers & Air Quality — Southern California
Observation period: Jan 15 – Mar 15, 2024

Research question: Is residential PM2.5 exposure associated with
reduced heart rate variability (HRV) and elevated resting heart
rate (RHR) in adults wearing activity trackers?

Updated by AERIS: PM2.5 exposure integrated from monitoring network.
DAG-informed adjustment set: age, sex, bmi, smoker, steps_per_day, sleep_hours
"""

import pandas as pd
from scipy import stats

# ── 0. Load cohort with PM2.5 exposure ─────────────────────────────────────
cohort = pd.read_csv("cohort_with_exposure.csv")
print(f"Cohort loaded: {len(cohort)} subjects")
print(f"Columns: {list(cohort.columns)}")
print()

# ── 1. BASELINE MODELS (no air quality) ─────────────────────────────────────
# Simple correlations: HRV ~ demographics + lifestyle
X_cols = ["age", "bmi", "steps_per_day", "sleep_hours"]
cohort["smoker_num"] = cohort["smoker"].astype(float)
cohort["sex_num"] = (cohort["sex"] == "F").astype(float)

print("=== Baseline: HRV correlations (no exposure data) ===")
for col in X_cols + ["smoker_num", "sex_num"]:
    r, p = stats.pearsonr(cohort[col], cohort["mean_hrv_ms"])
    print(f"  {col:>15s}:  r = {r:+.3f}  (p = {p:.3f})")

print()
print("=== Baseline: RHR correlations (no exposure data) ===")
for col in X_cols + ["smoker_num", "sex_num"]:
    r, p = stats.pearsonr(cohort[col], cohort["mean_rhr_bpm"])
    print(f"  {col:>15s}:  r = {r:+.3f}  (p = {p:.3f})")

# ── 2. PM2.5 EXPOSURE CORRELATIONS ──────────────────────────────────────────
print()
print("=== PM2.5 Exposure Distribution ===")
pm = cohort["pm25_mean"]
print(f"  Mean ± SD : {pm.mean():.2f} ± {pm.std():.2f} µg/m³")
print(f"  Range     : {pm.min():.2f} – {pm.max():.2f} µg/m³")
print(f"  P25 / P75 : {pm.quantile(0.25):.2f} / {pm.quantile(0.75):.2f} µg/m³")
print()

print("=== PM2.5 vs. Cardiac Outcomes ===")
r_hrv, p_hrv = stats.pearsonr(cohort["pm25_mean"], cohort["mean_hrv_ms"])
r_rhr, p_rhr = stats.pearsonr(cohort["pm25_mean"], cohort["mean_rhr_bpm"])
print(f"  PM2.5 ~ HRV (RMSSD):  r = {r_hrv:+.3f}  (p = {p_hrv:.3f})")
print(f"  PM2.5 ~ RHR:          r = {r_rhr:+.3f}  (p = {p_rhr:.3f})")
print()

# ── 3. ADJUSTED MODELS — DAG-informed adjustment set ────────────────────────
# Adjust for: age, sex, bmi, smoking, physical_activity, sleep
# Residualize outcome and exposure on covariates, then correlate (FWL theorem)
print("=== Adjusted Association: PM2.5 → HRV (partial correlation) ===")
print("    Adjustment set: age, sex, bmi, smoker, steps_per_day, sleep_hours")
print("    [DAG: confounders only; NOT adjusting for ANS/inflammation mediator]")
print()

covariates = ["age", "sex_num", "bmi", "smoker_num", "steps_per_day", "sleep_hours"]

def partial_corr(df, x_col, y_col, cov_cols):
    """Frisch-Waugh-Lovell partial correlation."""
    from numpy.linalg import lstsq
    import numpy as np
    Z = df[cov_cols].values
    Z = (Z - Z.mean(0)) / (Z.std(0) + 1e-9)
    Z = np.hstack([np.ones((len(Z), 1)), Z])
    x = df[x_col].values
    y = df[y_col].values
    res_x = x - Z @ lstsq(Z, x, rcond=None)[0]
    res_y = y - Z @ lstsq(Z, y, rcond=None)[0]
    return stats.pearsonr(res_x, res_y)

r_adj_hrv, p_adj_hrv = partial_corr(cohort, "pm25_mean", "mean_hrv_ms", covariates)
r_adj_rhr, p_adj_rhr = partial_corr(cohort, "pm25_mean", "mean_rhr_bpm", covariates)

print(f"  PM2.5 ~ HRV (adjusted):  r = {r_adj_hrv:+.3f}  (p = {p_adj_hrv:.3f})")
print(f"  PM2.5 ~ RHR (adjusted):  r = {r_adj_rhr:+.3f}  (p = {p_adj_rhr:.3f})")
print()
print("=== Interpretation ===")
if p_adj_hrv < 0.05:
    direction = "negative" if r_adj_hrv < 0 else "positive"
    print(f"  ✓ PM2.5 shows a significant {direction} association with HRV after adjustment.")
else:
    print(f"  ~ PM2.5–HRV association (r={r_adj_hrv:+.3f}) is not significant after adjustment.")
    print(f"    Small N (n=15) limits power; treat as pilot/directional evidence.")
if p_adj_rhr < 0.05:
    direction = "positive" if r_adj_rhr > 0 else "negative"
    print(f"  ✓ PM2.5 shows a significant {direction} association with RHR after adjustment.")
else:
    print(f"  ~ PM2.5–RHR association (r={r_adj_rhr:+.3f}) is not significant after adjustment.")
print()
print("NEXT STEPS:")
print("  1. Scale up cohort for adequate power (n≥100 recommended)")
print("  2. Run sensitivity analysis with NO2 as alternative exposure")
print("  3. Explore effect modification by smoking status (interaction term)")
print("  4. Consider mixed-effects model if adding longitudinal wearable data")

#!/usr/bin/env python3
"""Reanalysis workflow for PMID 38788590.

This program is deliberately fail-closed.  It documents the locked target and
the sanitization required before author-designated outcome/covariate data may
be inspected.  This campaign was terminated by the disk-space guard before any
health or exposure data could be downloaded, so it must not be used to create
an estimate.
"""
from pathlib import Path
import json

OUT = Path("/output")
FORBIDDEN = ("pollution", "pm25", "pm2.5", "exposure", "fitted", "prediction", "attribut", "lag")

def sanitize_columns(columns):
    """Return retained and dropped names before viewing/modeling a supplied table."""
    retained = [c for c in columns if not any(x in c.lower() for x in FORBIDDEN)]
    dropped = [c for c in columns if c not in retained]
    return {"retained_columns": retained, "dropped_columns": dropped}

def main():
    contract = {
        "outcome": "all cancer mortality (underlying ICD-10 C00-C97; site definitions reported separately)",
        "pollutant": "daily PM2.5",
        "geography": "Brazil, 5,570 municipalities; residence municipality",
        "period": "2000-01-01 through 2019-12-31",
        "unit": "individual death record with time-stratified case-crossover referent days",
        "exposure_assignment": "municipality population-weighted daily grid mean; primary lag 0-2 mean",
        "covariates": "daily mean temperature and relative humidity, modeled with natural splines (full degrees of freedom unavailable in supplied record)",
        "model": "conditional logistic regression, matched on time-stratified case-crossover strata",
        "primary_contrast": "10 micrograms/m3 increase in lag 0-2 PM2.5; OR = exp(10 * beta)"
    }
    (OUT / "locked_study_contract.json").write_text(json.dumps(contract, indent=2) + "\n")
    # No author-designated table was obtained.  The required audit is therefore
    # an empty, inspect-before-use record rather than inferred schema contents.
    (OUT / "sanitization_columns.json").write_text(json.dumps({
        "source_table": None, "retained_columns": [], "dropped_columns": [],
        "status": "not_run: no health/covariate table retrieved before policy termination"
    }, indent=2) + "\n")
    raise SystemExit("STOP: policy termination recorded; no panel/model may be constructed")

if __name__ == "__main__":
    main()

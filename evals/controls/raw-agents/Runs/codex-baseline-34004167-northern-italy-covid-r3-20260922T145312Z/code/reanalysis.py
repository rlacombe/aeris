#!/usr/bin/env python3
"""Rebuild the outcome-side panel and record fidelity for PMID 34004167.

This program deliberately does not fit the paper's GEE model unless every
required published component is present.  It is runnable from /output and
uses only the downloaded Civil Protection outcome release.
"""
from __future__ import annotations
import csv, hashlib, json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw" / "dpc-covid19-ita-regioni.csv"
START, END = date(2020, 2, 21), date(2020, 5, 19)
REGIONS = {"Lombardia", "Veneto"}

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def record_reanalysis_fidelity(panel_rows: int, included_dates: set[date]) -> dict:
    """Write a machine-readable protocol-fidelity assessment."""
    requested = {(START.fromordinal(START.toordinal()+i)).isoformat()
                 for i in range((END-START).days+1)}
    observed = {d.isoformat() for d in included_dates}
    out = {
        "study_id": "PMID_34004167",
        "published_contract": {
            "units": ["Lombardy", "Veneto"], "dates": "2020-02-21 through 2020-05-19",
            "outcomes": ["daily COVID-19 cases", "daily COVID-19 deaths", "fatality rate"],
            "exposures": ["daily STAP", "2013-2020 LTAP for NO2, O3, PM2.5, PM10, SO2"],
            "covariate": "LOCK=1 from 2020-02-22", "model": "log-link GEE, AR(1)"
        },
        "reconstructed": {"outcome_rows": panel_rows, "dates": f"{min(observed)} through {max(observed)}",
                          "dates_missing": sorted(requested-observed), "lock_values": [1]},
        "fidelity": "not fit: independent all-pollutant STAP/LTAP panel unavailable; outcome source has no LOCK=0 rows",
        "artifact_version": "1.0"
    }
    (ROOT / "fidelity_record.json").write_text(json.dumps(out, indent=2) + "\n")
    return out

def main() -> None:
    # Sanitization is explicit: preserve only outcome/date/region fields before inspection.
    retained = ["data", "denominazione_regione", "nuovi_positivi", "deceduti", "totale_casi"]
    with RAW.open(encoding="utf-8-sig", newline="") as f:
        original_columns = next(csv.reader(f))
    dropped = [c for c in original_columns if c not in retained]
    (ROOT / "outcome_sanitization.json").write_text(json.dumps({
        "source": str(RAW), "rule": "retain only date, region, and outcome fields; drop every other source column before analysis",
        "retained_columns": retained, "dropped_columns": dropped
    }, indent=2) + "\n")

    rows, dates = [], set()
    with RAW.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            d = date.fromisoformat(r["data"][:10])
            if r["denominazione_regione"] not in REGIONS or not (START <= d <= END):
                continue
            cases, deaths = int(r["nuovi_positivi"] or 0), int(r["deceduti"] or 0)
            rows.append({"date": d.isoformat(), "region": r["denominazione_regione"],
                         "daily_cases": cases, "cumulative_deaths": deaths,
                         "cumulative_cases": int(r["totale_casi"] or 0),
                         "fatality_rate_cumulative": (deaths / int(r["totale_casi"])) if int(r["totale_casi"] or 0) else "",
                         "lock": 1, "stap": "", "ltap": ""})
            dates.add(d)
    rows.sort(key=lambda x: (x["region"], x["date"]))
    previous_deaths = {}
    for r in rows:
        prior = previous_deaths.get(r["region"])
        r["daily_deaths_derived"] = "" if prior is None else r["cumulative_deaths"] - prior
        previous_deaths[r["region"]] = r["cumulative_deaths"]
    rows.sort(key=lambda x: (x["date"], x["region"]))
    with (ROOT / "analysis_panel.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    with (ROOT / "exposure_table.csv").open("w", newline="") as f:
        csv.DictWriter(f, fieldnames=["region", "date", "pollutant", "stap_ug_m3", "ltap_ug_m3", "source_status"]).writeheader()
    record_reanalysis_fidelity(len(rows), dates)
    (ROOT / "model_output.txt").write_text(
        "MODEL NOT EXECUTED\n"
        "The locked GEE needs STAP, LTAP, and LOCK. No independent public all-pollutant exposure panel was retrieved for both regions. "
        "The official outcome release starts 2020-02-24, after LOCK began 2020-02-22, so LOCK is identically 1 in all 172 reconstructed rows. "
        "Consequently the specified adjusted model cannot estimate its lockdown parameter, and an effect estimate/CI would be unsupported.\n")
    print(json.dumps({"status": "completed_blocker", "rows": len(rows), "sha256": sha256(RAW)}))

if __name__ == "__main__":
    main()

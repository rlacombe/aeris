"""Rebuild 2016-2019 municipal PM2.5 with AERIS for PMID 34260961.

The AERIS archive fallback deliberately bounds automatic S3 retrievals.  This
runner therefore makes four independent annual agent runs rather than one
four-year request.  It preserves the source substitution: no author exposure
surface is read at any point.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from aeris.agent.state import SessionState
from aeris.agentic.contract import execute

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - supplied by AERIS environment
    load_dotenv = None


RUN_DIRECTORY = Path(__file__).resolve().parent
ENV_PATH = Path(".env")
COHORT_PATH = RUN_DIRECTORY / "aeris_cohort.csv"
YEARS = (2016, 2017, 2018, 2019)


def call(trace: list[dict], state: SessionState, name: str, **arguments: object) -> dict:
    result = execute(state, name, arguments)
    trace.append({"tool": name, "arguments": arguments, "result": result})
    return result


def write_year_cohort(year: int) -> Path:
    """Create one bounded annual cohort without changing participant locations."""
    cohort = pd.read_csv(COHORT_PATH, dtype={"subject_id": str})
    cohort["start_date"] = f"{year}-01-01"
    cohort["end_date"] = f"{year}-12-31"
    path = RUN_DIRECTORY / f"aeris_cohort_{year}.csv"
    cohort.to_csv(path, index=False)
    return path


def summarize_spatial_variation(annual_paths: list[Path]) -> dict:
    """Write the study-period panel and an explicit identifiability audit."""
    annual = []
    for path in annual_paths:
        year = int(path.stem.rsplit("_", 1)[-1])
        frame = pd.read_csv(path, dtype={"subject_id": str})
        frame["year"] = year
        annual.append(frame)

    if not annual:
        raise RuntimeError("AERIS produced no annual output files.")
    panel = pd.concat(annual, ignore_index=True)
    panel.to_csv(RUN_DIRECTORY / "aeris_pm25_annual.csv", index=False)

    def weighted_mean(group: pd.DataFrame) -> float:
        weights = pd.to_numeric(group["n_samples"], errors="coerce").fillna(0)
        values = pd.to_numeric(group["mean"], errors="coerce")
        valid = values.notna() & (weights > 0)
        if not valid.any():
            return float("nan")
        return float((values[valid] * weights[valid]).sum() / weights[valid].sum())

    rows = []
    for subject_id, group in panel.groupby("subject_id", sort=True):
        rows.append(
            {
                "subject_id": subject_id,
                "pm25_2016_2019_ug_m3": weighted_mean(group),
                "n_years_observed": int(group["year"].nunique()),
                "n_daily_values": int(pd.to_numeric(group["n_samples"], errors="coerce").fillna(0).sum()),
                "station_ids": ";".join(sorted(set(group["station_id"].astype(str)))),
                "data_sources": ";".join(sorted(set(group["data_source"].astype(str)))),
            }
        )
    study_period = pd.DataFrame(rows)
    study_period.to_csv(RUN_DIRECTORY / "aeris_pm25_study_period.csv", index=False)

    yearly = []
    for year, group in panel.groupby("year", sort=True):
        values = pd.to_numeric(group["mean"], errors="coerce").dropna()
        yearly.append(
            {
                "year": int(year),
                "municipalities_with_pm25": int(values.size),
                "unique_station_assignments": int(group["station_id"].nunique()),
                "unique_exposure_values": int(values.nunique()),
                "municipal_exposure_sd": float(values.std(ddof=1)) if values.size > 1 else 0.0,
                "municipal_exposure_range": (
                    float(values.max() - values.min()) if values.size else float("nan")
                ),
                "n_s3_backed_rows": int(group["data_source"].fillna("").str.contains("archive").sum()),
                "data_sources": sorted(set(group["data_source"].dropna().astype(str))),
            }
        )
    exposure = pd.to_numeric(study_period["pm25_2016_2019_ug_m3"], errors="coerce").dropna()
    audit = {
        "study_pmid": "34260961",
        "exposure_window": "2016-01-01 through 2019-12-31",
        "assignment": "nearest current OpenAQ Israel catalog location within 25 km; annual AERIS S3 fallback enabled",
        "annual_runs": yearly,
        "study_period": {
            "municipalities_with_exposure": int(exposure.size),
            "unique_station_assignments": int(study_period["station_ids"].nunique()),
            "unique_exposure_values": int(exposure.nunique()),
            "municipal_exposure_sd": float(exposure.std(ddof=1)) if exposure.size > 1 else 0.0,
            "municipal_exposure_range": float(exposure.max() - exposure.min()) if exposure.size else float("nan"),
            "spatially_identifiable": bool(exposure.nunique() > 1),
        },
    }
    (RUN_DIRECTORY / "aeris_pm25_spatial_audit.json").write_text(
        json.dumps(audit, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return audit


def main() -> int:
    if load_dotenv is not None:
        load_dotenv(ENV_PATH, override=False)
    if not COHORT_PATH.exists():
        raise FileNotFoundError(f"Run build_public_inputs.py first: {COHORT_PATH}")

    trace: list[dict] = []
    annual_paths: list[Path] = []
    for year in YEARS:
        state = SessionState()
        state.working_directory = str(RUN_DIRECTORY)
        state.config.openaq_calls_per_minute = 20
        state.config.archive_fallback_max_days = 366
        state.config.archive_fallback_max_objects = 500
        cohort_path = write_year_cohort(year)
        call(trace, state, "load_cohort", path=str(cohort_path))
        call(
            trace,
            state,
            "plan_exposure",
            pollutant="pm25",
            country="il",
            n_stations=1,
            temporal_resolution="daily",
            location_strategy="catalog",
        )
        estimate = call(
            trace,
            state,
            "estimate_exposure",
            pollutant="pm25",
            country="il",
            n_stations=1,
            temporal_resolution="daily",
            location_strategy="catalog",
            researcher_approved=True,
        )
        output_path = RUN_DIRECTORY / f"aeris_pm25_{year}.csv"
        if estimate.get("status") == "ok":
            call(trace, state, "export_results", path=str(output_path))
            if output_path.exists():
                annual_paths.append(output_path)
        call(trace, state, "get_decision_log")

    audit = summarize_spatial_variation(annual_paths)
    (RUN_DIRECTORY / "aeris_tool_trace_historic.json").write_text(
        json.dumps(trace, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Input validation functions for the exposure estimator package.
"""

from pathlib import Path

import pandas as pd

from .exceptions import InputValidationError


def detect_mode(input_csv: str) -> str:
    """
    Detect whether input CSV is for static or dynamic mode based on columns.

    Args:
        input_csv: Path to input CSV file

    Returns:
        'static' or 'dynamic'

    Raises:
        InputValidationError: If schema is not recognized
    """
    p = Path(input_csv)
    if not p.exists():
        raise InputValidationError(f"CSV file not found: {input_csv}")

    df = pd.read_csv(p, dtype=str)

    # Check for dynamic mode (GPS schema)
    gps_cols = {"subject_id", "timestamp", "latitude", "longitude"}
    if gps_cols.issubset(df.columns):
        return "dynamic"

    # Check for static mode schema
    static_required = {"subject_id", "start_date", "end_date"}
    static_location = ({"zip", "address"} & set(df.columns)) or {
        "latitude",
        "longitude",
    }.issubset(df.columns)
    if static_required.issubset(df.columns) and static_location:
        return "static"

    raise InputValidationError(
        "Input schema not recognized. For static: subject_id, (zip|address|latitude+longitude), "
        "start_date, end_date. "
        "For dynamic: subject_id, timestamp, latitude, longitude."
    )


def validate_static_input(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and process static mode input DataFrame.

    Args:
        df: Raw input DataFrame

    Returns:
        Processed DataFrame with parsed dates and coordinates (if provided)

    Raises:
        InputValidationError: If validation fails
    """
    # Check required columns
    required = {"subject_id", "start_date", "end_date"}
    missing = required - set(df.columns)
    if missing:
        raise InputValidationError(f"Missing columns: {missing}")

    # Check location columns: either (zip OR address) OR (latitude AND longitude)
    has_geocode = bool({"zip", "address"} & set(df.columns))
    has_coords = {"latitude", "longitude"}.issubset(set(df.columns))

    if not (has_geocode or has_coords):
        raise InputValidationError(
            "Static mode requires either ('zip' or 'address') OR ('latitude' and 'longitude')."
        )

    # Parse dates
    df["start_dt"] = pd.to_datetime(df["start_date"], utc=True, errors="raise")
    df["end_dt"] = pd.to_datetime(df["end_date"], utc=True, errors="raise")

    # Check date consistency
    bad = df[df.end_dt < df.start_dt]
    if not bad.empty:
        raise InputValidationError(
            "end_date earlier than start_date for: " + ", ".join(bad.subject_id.tolist())
        )

    # Parse and validate coordinates if provided
    if has_coords:
        try:
            df["latitude"] = pd.to_numeric(df["latitude"], errors="raise")
            df["longitude"] = pd.to_numeric(df["longitude"], errors="raise")
        except (ValueError, TypeError) as e:
            raise InputValidationError(f"Invalid coordinate fields: {e}")

        # Geographic sanity checks
        bad_lat = df[(df["latitude"] < -90) | (df["latitude"] > 90)]
        bad_lon = df[(df["longitude"] < -180) | (df["longitude"] > 180)]
        if not bad_lat.empty:
            ids = ", ".join(bad_lat["subject_id"].astype(str).unique().tolist())
            raise InputValidationError(f"Latitude out of range for subject(s): {ids}")
        if not bad_lon.empty:
            ids = ", ".join(bad_lon["subject_id"].astype(str).unique().tolist())
            raise InputValidationError(f"Longitude out of range for subject(s): {ids}")

    return df


def validate_dynamic_input(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and process dynamic mode input DataFrame.

    Args:
        df: Raw input DataFrame

    Returns:
        Processed DataFrame with parsed coordinates and timestamps

    Raises:
        InputValidationError: If validation fails
    """
    # Check required columns
    gps_cols = {"subject_id", "timestamp", "latitude", "longitude"}
    if not gps_cols.issubset(df.columns):
        raise InputValidationError(
            "Dynamic mode requires columns: subject_id, timestamp, latitude, longitude"
        )

    # Parse timestamps and coordinates
    try:
        df["dt"] = pd.to_datetime(df["timestamp"], utc=True, errors="raise")
        df["latitude"] = pd.to_numeric(df["latitude"], errors="raise")
        df["longitude"] = pd.to_numeric(df["longitude"], errors="raise")
    except (ValueError, TypeError) as e:
        raise InputValidationError(f"Invalid GPS fields: {e}")

    # Geographic sanity checks
    bad_lat = df[(df["latitude"] < -90) | (df["latitude"] > 90)]
    bad_lon = df[(df["longitude"] < -180) | (df["longitude"] > 180)]
    if not bad_lat.empty:
        ids = ", ".join(bad_lat["subject_id"].astype(str).unique().tolist())
        raise InputValidationError(f"Latitude out of range for subject(s): {ids}")
    if not bad_lon.empty:
        ids = ", ".join(bad_lon["subject_id"].astype(str).unique().tolist())
        raise InputValidationError(f"Longitude out of range for subject(s): {ids}")

    # Per-subject hour deduplication
    df["hour"] = df["dt"].dt.floor("h")
    df = (
        df.drop_duplicates(subset=["subject_id", "hour"])
        .sort_values(["subject_id", "hour"])
        .reset_index(drop=True)
    )

    # Validate at least 1 row per subject after dedup
    for sid, grp in df.groupby("subject_id"):
        if len(grp) == 0:
            raise InputValidationError(
                f"Subject '{sid}' has no valid hourly points after deduplication."
            )

    return df

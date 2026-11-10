"""
Utility functions for the exposure estimator package.
"""

import functools
import logging
import math
import threading
import time
from typing import Any, Optional

import numpy as np
import pandas as pd
import pgeocode
import requests

from .exceptions import GeocodingError, UpstreamAPIError

logger = logging.getLogger(__name__)

_nominatim_lock = threading.Lock()
_nominatim_last_request = 0.0


def _wait_for_nominatim_slot() -> None:
    """Respect the public Nominatim service's one-request-per-second limit."""
    global _nominatim_last_request
    with _nominatim_lock:
        delay = 1.0 - (time.monotonic() - _nominatim_last_request)
        if delay > 0:
            time.sleep(delay)
        _nominatim_last_request = time.monotonic()


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth.

    Args:
        lat1, lon1: Latitude and longitude of first point
        lat2, lon2: Latitude and longitude of second point

    Returns:
        Distance in meters
    """
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6_371_000 * (2 * math.asin(math.sqrt(a)))


@functools.lru_cache(maxsize=256)
def geocode_zip(zip_code: str, country: str = "us") -> tuple[float, float]:
    """
    Geocode a ZIP/postal code using pgeocode.

    Results are cached (LRU, up to 256 entries) to avoid redundant network calls
    when multiple subjects share the same ZIP code.

    Args:
        zip_code: ZIP or postal code string
        country: ISO 3166-1 alpha-2 country code (default: "us")

    Returns:
        Tuple of (latitude, longitude)

    Raises:
        GeocodingError: If ZIP/postal code cannot be geocoded
    """
    nomi = pgeocode.Nominatim(country)
    res = nomi.query_postal_code(zip_code)
    if pd.isna(res.latitude) or pd.isna(res.longitude):
        raise GeocodingError(f"Invalid ZIP/postal code: {zip_code} (country={country})")
    return res.latitude, res.longitude


@functools.lru_cache(maxsize=256)
def geocode_address(address: str) -> tuple[float, float]:
    """
    Geocode a free-text address using OpenStreetMap Nominatim.

    Results are cached (LRU, up to 256 entries) to avoid redundant network calls
    when multiple subjects share the same address.

    Args:
        address: Free-text address string

    Returns:
        Tuple of (latitude, longitude)

    Raises:
        GeocodingError: If address cannot be geocoded
        UpstreamAPIError: If geocoding service fails
    """
    # Nominatim's public service permits at most one request per second.  The
    # cache above prevents duplicate lookups; this limiter protects distinct
    # cohort locations and lets a batch resume without triggering HTTP 429.
    _wait_for_nominatim_slot()
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": address, "format": "json", "limit": 1},
            headers={"User-Agent": "AERIS Exposure/1.0"},
            timeout=15,
        )
    except requests.RequestException as exc:
        raise UpstreamAPIError(f"Nominatim request failed: {exc}") from exc
    if r.status_code != 200:
        raise UpstreamAPIError(f"Nominatim HTTP {r.status_code}")

    data = r.json()
    if not data:
        raise GeocodingError(f"Address not found: {address}")

    return float(data[0]["lat"]), float(data[0]["lon"])


def pretty_pollutant(label: str) -> str:
    """
    Convert pollutant code to pretty display name with subscripts.

    Args:
        label: Pollutant code (e.g., 'pm25')

    Returns:
        Pretty formatted label (e.g., 'PM$_{2.5}$')
    """
    mapping = {
        "pm25": "PM$_{2.5}$",
        "pm10": "PM$_{10}$",
        "so2": "SO$_2$",
        "no2": "NO$_2$",
        "co": "CO",
        "o3": "O$_3$",
    }
    return mapping.get((label or "").lower(), (label or "").upper())


def prompt_user(msg: str) -> bool:
    """
    Simple interactive confirmation helper.

    Args:
        msg: Message to display to user

    Returns:
        True if user confirms with 'y' or 'yes', False otherwise
    """
    try:
        return input(f"{msg} [y/N]: ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


# EPA AQI breakpoint tables. Each entry is (C_lo, C_hi, I_lo, I_hi).
# PM2.5 (µg/m³, 24-hr), PM10 (µg/m³, 24-hr), SO2 (ppb, 1-hr), NO2 (ppb, 1-hr),
# CO (ppm, 8-hr), O3 (ppm, 8-hr)
_AQI_CATEGORIES = [
    (0, 50, "Good"),
    (51, 100, "Moderate"),
    (101, 150, "Unhealthy for Sensitive Groups"),
    (151, 200, "Unhealthy"),
    (201, 300, "Very Unhealthy"),
    (301, 500, "Hazardous"),
]

_AQI_BREAKPOINTS: dict[str, list[tuple[float, float, int, int]]] = {
    "pm25": [
        (0.0, 9.0, 0, 50),
        (9.1, 35.4, 51, 100),
        (35.5, 55.4, 101, 150),
        (55.5, 125.4, 151, 200),
        (125.5, 225.4, 201, 300),
        (225.5, 325.4, 301, 500),
    ],
    "pm10": [
        (0, 54, 0, 50),
        (55, 154, 51, 100),
        (155, 254, 101, 150),
        (255, 354, 151, 200),
        (355, 424, 201, 300),
        (425, 604, 301, 500),
    ],
    "so2": [
        (0, 35, 0, 50),
        (36, 75, 51, 100),
        (76, 185, 101, 150),
        (186, 304, 151, 200),
        (305, 604, 201, 300),
        (605, 1004, 301, 500),
    ],
    "no2": [
        (0, 53, 0, 50),
        (54, 100, 51, 100),
        (101, 360, 101, 150),
        (361, 649, 151, 200),
        (650, 1249, 201, 300),
        (1250, 2049, 301, 500),
    ],
    "co": [
        (0.0, 4.4, 0, 50),
        (4.5, 9.4, 51, 100),
        (9.5, 12.4, 101, 150),
        (12.5, 15.4, 151, 200),
        (15.5, 30.4, 201, 300),
        (30.5, 50.4, 301, 500),
    ],
    "o3": [
        (0.000, 0.054, 0, 50),
        (0.055, 0.070, 51, 100),
        (0.071, 0.085, 101, 150),
        (0.086, 0.105, 151, 200),
        (0.106, 0.200, 201, 300),
    ],
}


def concentration_to_aqi(concentration: float, pollutant: str) -> tuple[int, str]:
    """Convert pollutant concentration to EPA AQI value and category.

    Args:
        concentration: Pollutant concentration in standard units
            (PM2.5/PM10 in µg/m³, SO2/NO2 in ppb, CO in ppm, O3 in ppm)
        pollutant: Pollutant code (pm25, pm10, so2, no2, co, o3)

    Returns:
        Tuple of (aqi_value, category_string) e.g. (42, "Good")

    Raises:
        ValueError: If pollutant is unknown or concentration exceeds breakpoint table
    """
    key = pollutant.lower()
    if key not in _AQI_BREAKPOINTS:
        raise ValueError(f"Unknown pollutant '{pollutant}' for AQI conversion")

    breakpoints = _AQI_BREAKPOINTS[key]
    for c_lo, c_hi, i_lo, i_hi in breakpoints:
        if c_lo <= concentration <= c_hi:
            aqi = ((i_hi - i_lo) / (c_hi - c_lo)) * (concentration - c_lo) + i_lo
            aqi_int = round(aqi)
            # Find category
            category = "Hazardous"
            for cat_lo, cat_hi, cat_name in _AQI_CATEGORIES:
                if cat_lo <= aqi_int <= cat_hi:
                    category = cat_name
                    break
            return aqi_int, category

    raise ValueError(f"Concentration {concentration} exceeds AQI breakpoint table for {pollutant}")


def flag_outliers(
    values: pd.Series,
    iqr_factor: float = 1.5,
    remove_negative: bool = True,
) -> tuple[pd.Series, int]:
    """
    Flag and remove outliers from measurement values.

    Applies three checks:
    1. Remove negative values (sensor malfunctions)
    2. IQR-based flagging (values beyond Q1 - factor*IQR or Q3 + factor*IQR)

    Args:
        values: Series of numeric measurement values
        iqr_factor: IQR multiplier for outlier bounds (default: 1.5)
        remove_negative: Whether to remove negative values (default: True)

    Returns:
        Tuple of (cleaned values, number of outliers removed)
    """
    clean = values.copy()
    n_before = len(clean)

    if remove_negative:
        clean = clean[clean >= 0]

    q1 = clean.quantile(0.25)
    q3 = clean.quantile(0.75)
    iqr = q3 - q1
    lower = q1 - iqr_factor * iqr
    upper = q3 + iqr_factor * iqr
    clean = clean[(clean >= lower) & (clean <= upper)]

    return clean, n_before - len(clean)


def time_weighted_mean(timestamps: pd.Series, values: pd.Series) -> Optional[float]:
    """
    Compute a time-weighted average that accounts for temporal gaps.

    Each measurement's weight is proportional to the time interval it represents
    (half the gap to the previous + half the gap to the next measurement).

    Args:
        timestamps: Series of timezone-aware timestamps (sorted)
        values: Series of numeric values aligned with timestamps

    Returns:
        Time-weighted mean, or None if insufficient data
    """
    if len(timestamps) < 2:
        return float(values.iloc[0]) if len(values) == 1 else None

    ts = pd.Series(timestamps).sort_values().reset_index(drop=True)
    v = pd.Series(values).reset_index(drop=True)

    # Compute weights as half-intervals (seconds)
    diffs = ts.diff().dt.total_seconds().fillna(0).values
    weights = np.zeros(len(ts))
    for i in range(len(ts)):
        left = diffs[i] / 2 if i > 0 else 0
        right = diffs[i + 1] / 2 if i < len(ts) - 1 else 0
        weights[i] = left + right

    total_weight = weights.sum()
    if total_weight == 0:
        return float(v.mean())

    return float(np.average(v, weights=weights))


def idw_average(
    values: list[float],
    distances: list[float],
    power: float = 2.0,
) -> Optional[float]:
    """
    Compute inverse-distance-weighted average from multiple stations.

    Args:
        values: Measurement values from each station
        distances: Distances (meters) from subject to each station
        power: Distance weighting exponent (default: 2.0, standard in exposure science)

    Returns:
        IDW-weighted average, or None if no valid inputs
    """
    if not values or not distances:
        return None

    weights = []
    valid_values = []
    for v, d in zip(values, distances):
        if v is None or d is None:
            continue
        if d == 0:
            return float(v)  # Exact co-location
        weights.append(1.0 / (d**power))
        valid_values.append(v)

    if not weights:
        return None

    total_w = sum(weights)
    return float(sum(w * v for w, v in zip(weights, valid_values)) / total_w)


def idw_hourly_series(
    station_frames: list[pd.DataFrame],
    distances: list[float],
    pollutant: str,
    power: float = 2.0,
    outlier_detection: bool = False,
) -> pd.DataFrame:
    """
    Build an hour-aligned IDW exposure series from multiple station tidy frames.

    For each UTC hour, stations that reported are blended with inverse-distance
    weights (power=2 by default). Hours with no reporting stations are omitted.

    Args:
        station_frames: Tidy DataFrames with columns timestamp_utc, value, parameter
            (and optionally unit). One frame per station.
        distances: Distance in meters from the subject to each station (same order).
        pollutant: Pollutant name to keep (case-insensitive).
        power: IDW distance exponent.
        outlier_detection: If True, remove negatives/IQR outliers per station first.

    Returns:
        DataFrame with columns: timestamp_utc, value, parameter, unit, n_stations_hour.
        Empty DataFrame if no usable data.
    """
    empty_cols = ["timestamp_utc", "value", "parameter", "unit", "n_stations_hour"]
    if not station_frames or not distances or len(station_frames) != len(distances):
        return pd.DataFrame(columns=empty_cols)

    pol = (pollutant or "").lower()
    pieces: list[pd.DataFrame] = []

    for frame, dist in zip(station_frames, distances):
        if frame is None or frame.empty or dist is None:
            continue
        df = frame.copy()
        if "parameter" in df.columns:
            df["parameter"] = df["parameter"].astype(str).str.lower()
            df = df[df["parameter"] == pol]
        else:
            df["parameter"] = pol

        if df.empty:
            continue

        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["timestamp_utc", "value"])
        if df.empty:
            continue

        if outlier_detection:
            cleaned, _ = flag_outliers(df["value"])
            df = df.loc[cleaned.index]

        if df.empty:
            continue

        df["timestamp_utc"] = df["timestamp_utc"].dt.floor("h")
        if "unit" not in df.columns:
            df["unit"] = None

        # One value per station-hour
        agg = df.groupby("timestamp_utc", as_index=False).agg(
            value=("value", "mean"),
            unit=("unit", "first"),
        )
        agg["distance_m"] = float(dist)
        agg["parameter"] = pol
        pieces.append(agg)

    if not pieces:
        return pd.DataFrame(columns=empty_cols)

    long = pd.concat(pieces, ignore_index=True)

    rows = []
    for ts, grp in long.groupby("timestamp_utc"):
        blended = idw_average(grp["value"].tolist(), grp["distance_m"].tolist(), power=power)
        if blended is None:
            continue
        unit = None
        if not grp["unit"].isna().all():
            unit = grp["unit"].dropna().iloc[0]
        rows.append(
            {
                "timestamp_utc": ts,
                "value": blended,
                "parameter": pol,
                "unit": unit,
                "n_stations_hour": len(grp),
            }
        )

    if not rows:
        return pd.DataFrame(columns=empty_cols)

    return pd.DataFrame(rows).sort_values("timestamp_utc").reset_index(drop=True)


def calculate_metrics(
    df_vals: pd.DataFrame,
    pollutant: Optional[str] = None,
    threshold: Optional[float] = None,
    expected_hours: Optional[int] = None,
    outlier_detection: bool = False,
) -> dict:
    """
    Compute exposure metrics from measurement data.

    Args:
        df_vals: DataFrame with measurement data
        pollutant: Pollutant name to filter by
        threshold: Optional concentration threshold for exceedance counting
        expected_hours: Optional expected hours for completeness calculation
        outlier_detection: Whether to flag and remove outliers before computing stats

    Returns:
        Dictionary with mean, std, median, n_samples, min, max, percentiles,
        and optional exceedance, completeness, time-weighted, and outlier keys.
    """
    empty = {
        "mean": None,
        "std": None,
        "median": None,
        "n_samples": 0,
        "min": None,
        "max": None,
        "p5": None,
        "p25": None,
        "p75": None,
        "p95": None,
    }

    if df_vals is None or df_vals.empty:
        return empty

    df = df_vals.copy()

    # Normalize parameter column
    def _extract_param(x: Any) -> str:
        if isinstance(x, str):
            return x.lower()
        if isinstance(x, dict):
            return str(x.get("name", "")).lower()
        return str(getattr(x, "name", "")).lower()

    if "param" not in df.columns:
        if "parameter" in df.columns:
            df["param"] = df["parameter"].apply(_extract_param)
        else:
            df["param"] = (pollutant or "").lower()

    # Normalize timestamps
    if "timestamp_utc" in df.columns:
        df["ts"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce").dt.floor("h")
    elif "period" in df.columns:
        df["ts"] = pd.to_datetime(
            df["period"].apply(lambda p: p["datetime_from"]["utc"]), utc=True, errors="coerce"
        ).dt.floor("h")
    else:
        df["ts"] = pd.NaT

    # Filter and compute stats
    sub = df[(df["param"] == (pollutant or "").lower())].dropna(subset=["value"])
    if sub.empty:
        return empty

    vals = pd.to_numeric(sub["value"], errors="coerce").dropna()

    # Outlier detection
    n_outliers = 0
    if outlier_detection and len(vals) > 0:
        vals, n_outliers = flag_outliers(vals)
        if vals.empty:
            return empty

    n_hours = int(sub.dropna(subset=["ts"])["ts"].nunique())

    result = {
        "mean": float(vals.mean()),
        "std": float(vals.std(ddof=0)),
        "median": float(vals.median()),
        "n_samples": n_hours,
        "min": float(vals.min()),
        "max": float(vals.max()),
        "p5": float(vals.quantile(0.05)),
        "p25": float(vals.quantile(0.25)),
        "p75": float(vals.quantile(0.75)),
        "p95": float(vals.quantile(0.95)),
    }

    # Time-weighted mean (when timestamps are available)
    ts_valid = sub.dropna(subset=["ts"])
    if len(ts_valid) >= 2:
        tw_vals = pd.to_numeric(ts_valid["value"], errors="coerce").dropna()
        tw_ts = ts_valid.loc[tw_vals.index, "ts"]
        if len(tw_ts) >= 2:
            result["time_weighted_mean"] = time_weighted_mean(tw_ts, tw_vals)

    if outlier_detection:
        result["n_outliers_removed"] = n_outliers

    if threshold is not None:
        exceed = int((vals > threshold).sum())
        result["exceedance_count"] = exceed
        result["exceedance_pct"] = float(exceed / len(vals) * 100) if len(vals) > 0 else 0.0
        result["exceedance_threshold"] = float(threshold)

    if expected_hours is not None and expected_hours > 0:
        result["completeness_pct"] = round(n_hours / expected_hours * 100, 1)

    return result

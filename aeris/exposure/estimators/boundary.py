"""OpenAQ exposure estimation for explicit administrative boundaries."""

from __future__ import annotations

import contextlib
import json
import logging
import math
from datetime import timedelta
from typing import Any

import pandas as pd

from aeris.exposure.api_clients import OpenAQArchiveClient, RateLimitedOpenAQ
from aeris.exposure.boundaries import AdministrativeBoundary
from aeris.exposure.config import ALLOWED_POLLUTANTS, Config
from aeris.exposure.exceptions import ConfigurationError
from aeris.exposure.utils import concentration_to_aqi

from .static import ExposureEstimatorOpenAQStatic

logger = logging.getLogger(__name__)


class ExposureEstimatorOpenAQBoundary:
    """Compute a monitor-network exposure record for one named polygon.

    The estimand is the unweighted mean of monitor-level means for monitors
    whose coordinates fall within the supplied boundary. This is a network
    summary, not a population-weighted area concentration or personal dose.
    """

    def __init__(
        self,
        boundary: AdministrativeBoundary,
        start_date: str,
        end_date: str,
        pollutant: str,
        api_key: str | None = None,
        config: Config | None = None,
        min_completeness: float | None = None,
        cache=None,
        temporal_resolution: str = "hourly",
        max_stations: int | None = None,
    ) -> None:
        pollutant = pollutant.lower()
        if pollutant not in ALLOWED_POLLUTANTS:
            raise ConfigurationError(
                f"Invalid pollutant '{pollutant}'. Choose one of: {', '.join(ALLOWED_POLLUTANTS)}"
            )
        self.boundary = boundary
        self.pollutant = pollutant
        self.start_dt = pd.Timestamp(start_date, tz="UTC")
        self.end_dt = pd.Timestamp(end_date, tz="UTC")
        if self.end_dt < self.start_dt:
            raise ConfigurationError("end_date must be on or after start_date.")
        if min_completeness is not None and not 0 <= min_completeness <= 100:
            raise ConfigurationError("min_completeness must be between 0 and 100.")

        self.config = config or Config.from_env()
        if api_key:
            self.config.openaq_api_key = api_key
        if not self.config.openaq_api_key:
            raise ConfigurationError("Missing OpenAQ API key (flag or OPENAQ_API_KEY env var).")

        self.client = RateLimitedOpenAQ(self.config.openaq_api_key, self.config)
        # Archive objects can be slow to open from public S3. Use a bounded
        # but practical timeout rather than the short API connection timeout.
        self.archive_client = OpenAQArchiveClient(timeout=(5.0, 20.0), max_retries=2)
        self.min_completeness = min_completeness
        self.cache = cache
        if temporal_resolution not in {"hourly", "daily"}:
            raise ConfigurationError("temporal_resolution must be 'hourly' or 'daily'.")
        self.temporal_resolution = temporal_resolution
        if max_stations is not None and max_stations < 1:
            raise ConfigurationError("max_stations must be at least 1.")
        self.max_stations = max_stations
        self.n_stations_available = 0
        self._raw_data = pd.DataFrame()
        self._station_summary = pd.DataFrame()
        self._archive_reports: list[dict[str, Any]] = []

    def estimate_api_calls(self) -> tuple[int, float, float]:
        """Estimate calls after monitor discovery; call after ``discover_stations``."""
        stations = self.discover_stations()
        expected_observations = (
            self._expected_hours if self.temporal_resolution == "hourly" else self._expected_days
        )
        pages_per_station = max(1, (expected_observations + 999) // 1000)
        calls = 1 + len(stations) * pages_per_station
        minutes = max(
            calls / self.config.openaq_calls_per_minute,
            (calls / self.config.openaq_calls_per_hour) * 60,
        )
        return calls, minutes, minutes / 60

    @property
    def _expected_hours(self) -> int:
        return int((self.end_dt - self.start_dt).total_seconds() // 3600) + 24

    @property
    def _expected_days(self) -> int:
        return (self.end_dt.date() - self.start_dt.date()).days + 1

    def discover_stations(self) -> list[dict[str, Any]]:
        """Find OpenAQ locations in the boundary and compatible pollutant sensors."""
        # The OpenAQ client validates bbox strictly as a tuple, while the API
        # itself serializes it as four comma-separated values.
        bbox_values = tuple(round(value, 4) for value in self.boundary.bbox)
        cache_key = {
            "endpoint": "boundary_locations",
            "bbox": ",".join(str(value) for value in bbox_values),
            "pollutant": self.pollutant,
        }
        locations = self.cache.get(**cache_key) if self.cache else None
        if locations is None:
            locations = []
            page = 1
            while len(locations) < self.config.station_limit:
                response = self.client.list_locations(
                    bbox=bbox_values,
                    limit=min(1000, self.config.station_limit - len(locations)),
                    page=page,
                )
                batch = list(response.results or [])
                locations.extend(batch)
                if len(batch) < 1000:
                    break
                page += 1
            if self.cache:
                self.cache.put(locations, **cache_key)

        stations: list[dict[str, Any]] = []
        for location in locations:
            latitude, longitude = _location_coordinates(location)
            if latitude is None or longitude is None or not self.boundary.contains(latitude, longitude):
                continue
            if not _location_overlaps_period(location, self.start_dt, self.end_dt):
                continue
            sensor = next(
                (
                    item
                    for item in (_get(location, "sensors") or [])
                    if _parameter_name(item).lower() == self.pollutant
                ),
                None,
            )
            if sensor is None:
                continue
            stations.append(
                {
                    "location_id": _get(location, "id"),
                    "location_name": _get(location, "name"),
                    "sensor_id": _get(sensor, "id"),
                    "latitude": latitude,
                    "longitude": longitude,
                    "unit": _parameter_units(sensor),
                    "location_datetime_first": _datetime_value(
                        _get(location, "datetime_first") or _get(location, "datetimeFirst")
                    ),
                    "location_datetime_last": _datetime_value(
                        _get(location, "datetime_last") or _get(location, "datetimeLast")
                    ),
                }
            )
        stations.sort(key=_station_sort_key)
        self.n_stations_available = len(stations)
        if self.max_stations is not None and len(stations) > self.max_stations:
            stations = _spatially_balanced_stations(
                stations, self.max_stations, self.boundary.geometry.centroid
            )
        return stations

    def run(self) -> pd.DataFrame:
        """Collect boundary monitors and return one explicit network-summary row."""
        stations = self.discover_stations()
        if not stations:
            return self._empty_result("NO_STATIONS")

        frames: list[pd.DataFrame] = []
        for station in stations:
            frame = self._fetch_sensor_hours(station)
            if not frame.empty:
                frames.append(frame)
        if not frames:
            return self._empty_result("NO_OBSERVATIONS", n_stations=len(stations))

        raw = pd.concat(frames, ignore_index=True)
        units = raw["unit"].dropna().unique().tolist()
        if len(units) > 1:
            raise ConfigurationError(
                f"Cannot aggregate boundary monitors with incompatible units: {units}"
            )
        self._raw_data = raw.sort_values(["timestamp_utc", "location_id"]).reset_index(drop=True)
        self._station_summary = self._summarize_stations(self._raw_data)
        return self._summary_result()

    def _fetch_sensor_hours(self, station: dict[str, Any]) -> pd.DataFrame:
        start_dt = self.start_dt.to_pydatetime()
        end_dt = (self.end_dt + timedelta(days=1)).to_pydatetime()
        start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        cache_key = {
            "endpoint": (
                "boundary_sensor_days_v3"
                if self.temporal_resolution == "daily"
                else "boundary_sensor_hours_v3"
            ),
            "sensor_id": station["sensor_id"],
            "datetime_from": start_iso,
            "datetime_to": end_iso,
            "data": self.temporal_resolution,
        }
        rows = self.cache.get(**cache_key) if self.cache else None
        if rows is None:
            rows = []
            page = 1
            while True:
                if self.temporal_resolution == "daily":
                    response = self.client.list_daily_measurements(
                        sensor_id=station["sensor_id"],
                        date_from=start_dt.date().isoformat(),
                        date_to=(end_dt - timedelta(days=1)).date().isoformat(),
                        limit=1000,
                        page=page,
                    )
                else:
                    response = self.client.list_measurements(
                        sensors_id=station["sensor_id"],
                        data="hours",
                        datetime_from=start_dt,
                        datetime_to=end_dt,
                        limit=1000,
                        page=page,
                    )
                batch = list(response.results or [])
                if not batch:
                    break
                rows.extend(batch)
                if len(batch) < 1000:
                    break
                page += 1
            if self.cache and rows:
                self.cache.put(rows, **cache_key)
        if not rows:
            rows = self._fetch_archive_daily_range(
                station["location_id"], self.pollutant, start_dt, end_dt
            )
        elif self.temporal_resolution == "daily":
            v3_dates = _measurement_dates(rows)
            if len(v3_dates) < self._expected_days:
                archive_rows = self._fetch_archive_daily_range(
                    station["location_id"], self.pollutant, start_dt, end_dt
                )
                if archive_rows:
                    rows = ExposureEstimatorOpenAQStatic.normalize_measurement_records(rows)
                    rows.extend(row for row in archive_rows if _measurement_date(row) not in v3_dates)
        if not rows:
            return pd.DataFrame()

        tidy = ExposureEstimatorOpenAQStatic._tidy_raw_df(pd.DataFrame(rows))
        tidy["timestamp_utc"] = pd.to_datetime(tidy["timestamp_utc"], utc=True)
        for key, value in station.items():
            tidy[key] = value
        return tidy

    def _fetch_archive_daily_range(
        self, location_id: int, parameter: str, start_dt, end_dt
    ) -> list[dict[str, Any]]:
        """Recover a bounded historical series or plan a larger S3 retrieval."""
        if not self.config.archive_fallback_enabled:
            return []
        start_date = start_dt.date()
        end_date = (end_dt - timedelta(days=1)).date()
        dates_key = {
            "endpoint": "boundary_location_archive_available_dates_v1",
            "location_id": location_id,
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat(),
        }
        available_dates = self.cache.get(**dates_key) if self.cache else None
        if available_dates is None:
            available_dates = self.archive_client.list_available_dates(location_id, start_date, end_date)
            if self.cache:
                self.cache.put(available_dates, **dates_key)
        if not available_dates:
            self._archive_reports.append(
                {
                    "location_id": location_id,
                    "parameter": parameter,
                    "status": "no_archive_objects",
                    "available_objects": 0,
                    "recovered_days": 0,
                }
            )
            return []
        rows = self.archive_client.fetch_daily_range_checkpointed(
            location_id,
            parameter=parameter,
            available_dates=available_dates,
            chunk_size=self.config.archive_fallback_max_objects,
            cache=self.cache,
            cache_namespace="boundary_location_archive_daily_chunk_v1",
        )
        if self.archive_client.last_errors:
            logger.warning(
                "Archive fallback recovered a partial %s series for boundary location %s; "
                "%d location-day objects remain retryable.",
                parameter, location_id, len(self.archive_client.last_errors),
            )
        if rows:
            logger.info(
                "Recovered %d daily %s values from the OpenAQ S3 archive for boundary "
                "location %s.",
                len(rows),
                parameter,
                location_id,
            )
        self._archive_reports.append(
            {
                "location_id": location_id,
                "parameter": parameter,
                "status": "recovered" if rows else "objects_without_requested_parameter",
                "available_objects": len(available_dates),
                "recovered_days": len(rows),
                "failed_objects": len(self.archive_client.last_errors),
            }
        )
        return rows

    def _summarize_stations(self, raw: pd.DataFrame) -> pd.DataFrame:
        summary = (
            raw.groupby(["location_id", "location_name", "sensor_id", "latitude", "longitude", "unit"])[
                "value"
            ]
            .agg(["mean", "std", "min", "max", "count"])
            .reset_index()
            .rename(columns={"count": "n_hourly_observations", "mean": "station_mean"})
        )
        days = raw.assign(date=raw["timestamp_utc"].dt.date).groupby("location_id")["date"].nunique()
        summary["n_observed_days"] = summary["location_id"].map(days)
        expected_observations = (
            self._expected_hours if self.temporal_resolution == "hourly" else self._expected_days
        )
        summary["temporal_coverage_pct"] = (
            100 * summary["n_hourly_observations"] / expected_observations
        ).clip(upper=100)
        return summary

    def _summary_result(self) -> pd.DataFrame:
        station_means = self._station_summary["station_mean"].dropna()
        network_hours = self._raw_data["timestamp_utc"].nunique()
        expected_observations = (
            self._expected_hours if self.temporal_resolution == "hourly" else self._expected_days
        )
        coverage_pct = min(100.0, 100 * network_hours / expected_observations)
        mean = float(station_means.mean()) if not station_means.empty else None
        aqi, category = None, None
        if mean is not None:
            with contextlib.suppress(ValueError):
                aqi, category = concentration_to_aqi(mean, self.pollutant)
        qc_flag = "NOT_SET"
        if self.min_completeness is not None:
            qc_flag = "PASS" if coverage_pct >= self.min_completeness else "FAIL"
        return pd.DataFrame(
            [
                {
                    "boundary_name": self.boundary.name,
                    "pollutant": self.pollutant,
                    "start_date": self.start_dt.date().isoformat(),
                    "end_date": self.end_dt.date().isoformat(),
                    "aggregation": "unweighted_mean_of_station_means",
                    "mean": mean,
                    "std_across_stations": float(station_means.std()) if len(station_means) > 1 else None,
                    "n_stations": len(self._station_summary),
                    "n_stations_available": self.n_stations_available,
                    "max_stations": self.max_stations,
                    "station_selection": (
                        "deterministic_spatial_spread"
                        if self.max_stations is not None
                        and self.n_stations_available > self.max_stations
                        else "all_eligible_stations"
                    ),
                    "n_hourly_observations": len(self._raw_data),
                    "network_hours_observed": network_hours,
                    "expected_hours": self._expected_hours,
                    "temporal_resolution": self.temporal_resolution,
                    "n_observations": len(self._raw_data),
                    "network_observations": network_hours,
                    "expected_observations": expected_observations,
                    "network_temporal_coverage_pct": coverage_pct,
                    "min_completeness_pct": self.min_completeness,
                    "qc_flag": qc_flag,
                    "unit": self._raw_data["unit"].dropna().iloc[0]
                    if not self._raw_data["unit"].dropna().empty
                    else None,
                    "aqi": aqi,
                    "aqi_category": category,
                    "data_source": ";".join(sorted(self._raw_data["data_source"].dropna().unique())),
                    "archive_retrieval": json.dumps(self._archive_reports, sort_keys=True),
                    "boundary_provenance": json.dumps(self.boundary.provenance(), sort_keys=True),
                }
            ]
        )

    def _empty_result(self, qc_flag: str, n_stations: int = 0) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "boundary_name": self.boundary.name,
                    "pollutant": self.pollutant,
                    "start_date": self.start_dt.date().isoformat(),
                    "end_date": self.end_dt.date().isoformat(),
                    "aggregation": "unweighted_mean_of_station_means",
                    "mean": None,
                    "n_stations": n_stations,
                    "n_stations_available": self.n_stations_available,
                    "max_stations": self.max_stations,
                    "station_selection": (
                        "deterministic_spatial_spread"
                        if self.max_stations is not None
                        and self.n_stations_available > self.max_stations
                        else "all_eligible_stations"
                    ),
                    "temporal_resolution": self.temporal_resolution,
                    "network_temporal_coverage_pct": 0.0,
                    "min_completeness_pct": self.min_completeness,
                    "qc_flag": qc_flag,
                    "archive_retrieval": json.dumps(self._archive_reports, sort_keys=True),
                    "boundary_provenance": json.dumps(self.boundary.provenance(), sort_keys=True),
                }
            ]
        )

    def get_raw_data(self) -> pd.DataFrame:
        """Return normalized observations with contributing station metadata."""
        return self._raw_data.copy()

    def get_daily_data(self) -> pd.DataFrame:
        """Return a daily network series using the documented boundary estimand.

        For each day, each station first contributes its hourly mean; the day
        is then the unweighted mean of those station-day means. This preserves
        the boundary estimator's monitor-weighted interpretation and exposes
        the series needed for time-series analysis.
        """
        if self._raw_data.empty:
            observation_column = (
                "n_hourly_observations"
                if self.temporal_resolution == "hourly"
                else "n_daily_observations"
            )
            return pd.DataFrame(
                columns=["date", "mean", "n_stations", observation_column, "unit"]
            )
        station_daily = (
            self._raw_data.assign(date=self._raw_data["timestamp_utc"].dt.date)
            .groupby(["date", "location_id", "unit"], as_index=False)["value"]
            .mean()
            .rename(columns={"value": "station_daily_mean"})
        )
        daily = (
            station_daily.groupby(["date", "unit"], as_index=False)["station_daily_mean"]
            .agg(mean="mean", n_stations="count")
        )
        hours = self._raw_data.assign(date=self._raw_data["timestamp_utc"].dt.date).groupby(
            "date"
        ).size()
        observation_column = (
            "n_hourly_observations"
            if self.temporal_resolution == "hourly"
            else "n_daily_observations"
        )
        daily[observation_column] = daily["date"].map(hours)
        daily["date"] = daily["date"].astype(str)
        return daily.sort_values("date").reset_index(drop=True)

    def get_station_info(self) -> pd.DataFrame:
        """Return one coverage/provenance row for each contributing monitor."""
        return self._station_summary.copy()


def _get(value: Any, field: str) -> Any:
    return value.get(field) if isinstance(value, dict) else getattr(value, field, None)


def _station_sort_key(station: dict[str, Any]) -> tuple[str, str]:
    """Stable tie-break key independent of provider response order."""
    return (str(station.get("location_id") or ""), str(station.get("sensor_id") or ""))


def _spatially_balanced_stations(stations: list[dict[str, Any]], limit: int, centroid) -> list[dict[str, Any]]:
    """Select a deterministic, spatially spread subset of eligible stations."""
    remaining = list(stations)
    first = min(
        remaining,
        key=lambda station: (
            _great_circle_km(
                float(station["latitude"]), float(station["longitude"]),
                float(centroid.y), float(centroid.x),
            ),
            _station_sort_key(station),
        ),
    )
    selected = [first]
    remaining.remove(first)
    while remaining and len(selected) < limit:
        candidate = min(
            remaining,
            key=lambda station: (
                -sum(
                    _great_circle_km(
                        float(station["latitude"]), float(station["longitude"]),
                        float(chosen["latitude"]), float(chosen["longitude"]),
                    )
                    for chosen in selected
                ),
                _station_sort_key(station),
            ),
        )
        selected.append(candidate)
        remaining.remove(candidate)
    return selected


def _great_circle_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance used only to distribute selected monitors."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _location_coordinates(location: Any) -> tuple[float | None, float | None]:
    coordinates = _get(location, "coordinates")
    if not coordinates:
        return None, None
    latitude = _get(coordinates, "latitude")
    longitude = _get(coordinates, "longitude")
    if latitude is None or longitude is None:
        return None, None
    return float(latitude), float(longitude)


def _parameter_name(sensor: Any) -> str:
    parameter = _get(sensor, "parameter")
    return str(_get(parameter, "name") or "")


def _parameter_units(sensor: Any) -> Any:
    parameter = _get(sensor, "parameter")
    units = _get(parameter, "units")
    return units[0] if isinstance(units, list) and units else units


def _location_overlaps_period(location: Any, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> bool:
    """Exclude a location only when its documented OpenAQ coverage cannot overlap."""
    first = _as_utc_timestamp(
        _get(location, "datetime_first") or _get(location, "datetimeFirst")
    )
    last = _as_utc_timestamp(_get(location, "datetime_last") or _get(location, "datetimeLast"))
    end_exclusive = end_dt + timedelta(days=1)
    return not ((first is not None and first >= end_exclusive) or (last is not None and last < start_dt))


def _datetime_value(value: Any) -> str | None:
    timestamp = _as_utc_timestamp(value)
    return timestamp.isoformat() if timestamp is not None else None


def _as_utc_timestamp(value: Any) -> pd.Timestamp | None:
    if not value:
        return None
    if isinstance(value, dict):
        value = value.get("utc") or value.get("local")
    else:
        value = _get(value, "utc") or _get(value, "local") or value
    try:
        return pd.Timestamp(value, tz="UTC")
    except (TypeError, ValueError):
        return None


def _measurement_date(record: Any):
    """Return the provider calendar day for a v3 or archive measurement."""
    period = _get(record, "period")
    datetime_from = _get(period, "datetime_from") or _get(period, "datetimeFrom")
    timestamp = _as_utc_timestamp(datetime_from)
    return timestamp.date() if timestamp is not None else None


def _measurement_dates(records: list[Any]) -> set:
    """Collect valid measurement days without assuming a provider response shape."""
    return {value for record in records if (value := _measurement_date(record)) is not None}

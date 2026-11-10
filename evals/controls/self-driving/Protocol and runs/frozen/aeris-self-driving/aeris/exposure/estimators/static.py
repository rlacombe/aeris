"""
Static mode estimator classes for exposure estimation.
"""

import contextlib
import json
import logging
import math
import sys
import warnings
from dataclasses import asdict, is_dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd
from tqdm import tqdm

from ..api_clients import OpenAQArchiveClient, RateLimitedOpenAQ
from ..config import ALLOWED_POLLUTANTS, Config
from ..exceptions import ConfigurationError, GeocodingError
from ..plotting import StaticPlotter
from ..utils import (
    calculate_metrics,
    concentration_to_aqi,
    geocode_address,
    geocode_zip,
    haversine,
    idw_average,
    idw_hourly_series,
    pretty_pollutant,
    prompt_user,
)
from ..validators import validate_static_input

logger = logging.getLogger(__name__)


def _record_value(record: Any, key: str) -> Any:
    """Read a provider field from dictionaries and SDK response objects."""
    if isinstance(record, dict):
        return record.get(key)
    return getattr(record, key, None)


def _measurement_date(record: Any):
    """Return the provider calendar day for a v3 or archive measurement."""
    period = _record_value(record, "period")
    datetime_from = _record_value(period, "datetime_from") or _record_value(period, "datetimeFrom")
    utc = _record_value(datetime_from, "utc") or _record_value(datetime_from, "local") or datetime_from
    try:
        timestamp = pd.Timestamp(utc, tz="UTC")
    except (TypeError, ValueError):
        return None
    return timestamp.date()


def _measurement_dates(records: list[Any]) -> set:
    """Collect valid measurement days without assuming a provider response shape."""
    return {value for record in records if (value := _measurement_date(record)) is not None}


def _measurement_mapping(record: Any) -> dict[str, Any]:
    """Normalize SDK and archive records before combining provider responses."""
    if isinstance(record, dict):
        return record
    if is_dataclass(record):
        return asdict(record)
    if hasattr(record, "model_dump"):
        return record.model_dump()
    if hasattr(record, "dict"):
        return record.dict()
    raise TypeError(f"Unsupported OpenAQ measurement record: {type(record)!r}")


def _as_utc_timestamp(value: Any) -> pd.Timestamp | None:
    """Normalize provider date fields for catalog coverage checks."""
    if not value:
        return None
    if isinstance(value, dict):
        value = value.get("utc") or value.get("local")
    else:
        value = _record_value(value, "utc") or _record_value(value, "local") or value
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")

# Silence pandas FutureWarning about downcasting in replace to keep console clean for users
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message=r".*Downcasting behavior in `replace` is deprecated.*",
)


class ExposureEstimatorOpenAQStatic:
    """
    Static mode estimator using OpenAQ API.

    Processes subjects with ZIP codes, addresses, or coordinates and date ranges,
    fetching hourly measurements for one pollutant.

    Args:
        input_csv: Input data as a pandas DataFrame, CSV file path (str), or Path object.
                  DataFrame should have columns: subject_id, start_date, end_date, and either:
                  - (zip or address) for geocoding, OR
                  - (latitude and longitude) for direct coordinate use
        pollutant: Pollutant to analyze (pm25, pm10, so2, no2, co, o3)
        api_key: Optional OpenAQ API key (overrides environment variable)
        distance_threshold_km: Optional distance threshold for filtering subjects (km)
        config: Optional Config object (defaults to Config.from_env())
    """

    def __init__(
        self,
        input_csv: Union[str, Path, pd.DataFrame],
        pollutant: str,
        api_key: Optional[str] = None,
        distance_threshold_km: Optional[float] = None,
        config: Optional[Config] = None,
        country: str = "us",
        min_completeness: Optional[float] = None,
        cache=None,
        n_stations: int = 1,
        outlier_detection: bool = False,
        temporal_resolution: str = "hourly",
        location_strategy: str = "auto",
        catalog_min_subjects: int = 25,
        search_radius_km: Optional[float] = None,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> None:
        # Auto-configure logging if not already configured
        root_logger = logging.getLogger()
        if not root_logger.handlers:
            logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

        logger.info("Initialising ExposureEstimator (OpenAQ · STATIC)")

        # Validate pollutant
        pollutant = pollutant.lower()
        if pollutant == "all":
            self.pollutants = list(ALLOWED_POLLUTANTS)
            self.pollutant = "all"
        elif pollutant in ALLOWED_POLLUTANTS:
            self.pollutants = [pollutant]
            self.pollutant = pollutant
        else:
            raise ConfigurationError(
                f"Invalid pollutant '{pollutant}'. Choose one of: {', '.join(ALLOWED_POLLUTANTS)}, all"
            )

        self.input_csv = input_csv
        self.distance_threshold_km = distance_threshold_km
        self.country = country
        self.min_completeness = min_completeness
        self.cache = cache
        self.n_stations = max(1, n_stations)
        self.outlier_detection = outlier_detection
        if temporal_resolution not in {"hourly", "daily"}:
            raise ConfigurationError("temporal_resolution must be 'hourly' or 'daily'.")
        if location_strategy not in {"auto", "per_subject", "catalog"}:
            raise ConfigurationError(
                "location_strategy must be 'auto', 'per_subject', or 'catalog'."
            )
        self.temporal_resolution = temporal_resolution
        self.location_strategy = location_strategy
        self.catalog_min_subjects = max(1, catalog_min_subjects)
        self._measurement_memory: dict[tuple[Any, ...], list[Any]] = {}
        self._catalog_locations: list[Any] | None = None
        self._catalog_used = False
        self.output_dir = Path(output_dir) if output_dir else None
        if self.output_dir is not None:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        # Configuration
        self.config = config or Config.from_env()
        if search_radius_km is not None and not 0 < search_radius_km <= 200:
            raise ConfigurationError("search_radius_km must be greater than 0 and at most 200.")
        self.search_radius_m = int(
            search_radius_km * 1000 if search_radius_km is not None else self.config.search_radius
        )
        if api_key:
            self.config.openaq_api_key = api_key

        if not self.config.openaq_api_key:
            raise ConfigurationError("Missing OpenAQ API key (flag or OPENAQ_API_KEY env var).")

        # Initialize API client
        self.client = RateLimitedOpenAQ(self.config.openaq_api_key, self.config)
        # Archive objects can be slow to open from public S3. Use a bounded
        # but practical timeout rather than the short API connection timeout.
        self.archive_client = OpenAQArchiveClient(timeout=(5.0, 20.0), max_retries=2)

        # Initialize plotter (use first pollutant for single, or pm25 as default for "all")
        self.plotter = StaticPlotter(self.pollutants[0], output_dir=self.output_dir)

        # Data storage
        self.df_input: Optional[pd.DataFrame] = None
        self.results: list[dict] = []
        self._per_subject_tidy: dict[str, list[pd.DataFrame]] = {}
        self._per_subject_idw: dict[str, list[pd.DataFrame]] = {}

    def read_and_validate_input(self) -> None:
        """Load and validate static input (DataFrame or CSV path)."""
        # Handle DataFrame input
        if isinstance(self.input_csv, pd.DataFrame):
            logger.info("Reading input DataFrame (%d rows)", len(self.input_csv))
            # Make a copy to avoid modifying the original
            df = self.input_csv.copy()
            # Convert all columns to string to match CSV dtype=str behavior
            # This ensures consistent behavior whether input is CSV or DataFrame
            for col in df.columns:
                df[col] = df[col].astype(str)
            self.df_input = validate_static_input(df)
            logger.info("Mode locked: STATIC (OpenAQ)")
            return

        # Handle file path input
        logger.info("Reading CSV: %s", self.input_csv)
        p = Path(self.input_csv)
        if not p.exists():
            raise ConfigurationError(f"CSV file not found: {self.input_csv}")

        df = pd.read_csv(p, dtype=str)
        self.df_input = validate_static_input(df)
        logger.info("Mode locked: STATIC (OpenAQ)")

    def estimate_api_calls(self) -> tuple[int, float, float]:
        """
        Estimate number of API calls needed.

        Returns:
            Tuple of (calls, minutes, hours)
        """
        if self.df_input is None:
            raise RuntimeError("read_and_validate_input() must be called first")

        n_pollutants = len(self.pollutants)
        observations_per_day = 24 if self.temporal_resolution == "hourly" else 1
        calls = 0
        for _, row in self.df_input.iterrows():
            observations = ((row.end_dt - row.start_dt).days + 1) * observations_per_day
            pages = math.ceil(observations / 1_000)
            calls += 1 + pages * n_pollutants  # direct-discovery upper bound

        # Catalog mode replaces one location query per participant with a
        # bounded country-catalog retrieval. Measurement calls remain an upper
        # bound until station assignment deduplicates identical sensors.
        if self._use_catalog():
            catalog_pages = 10  # safety cap; execution falls back if exceeded
            calls = max(1, calls - len(self.df_input) + catalog_pages)

        minutes = max(
            calls / self.config.openaq_calls_per_minute,
            (calls / self.config.openaq_calls_per_hour) * 60,
        )
        return calls, minutes, minutes / 60

    @staticmethod
    def _tidy_raw_df(dfm: pd.DataFrame) -> pd.DataFrame:
        """Convert OpenAQ measurements to tidy format."""
        tidy = (
            pd.DataFrame(
                {
                    "timestamp_utc": dfm["period"].apply(
                        lambda p: (
                            p["datetime_from"]["utc"]
                            if isinstance(p, dict)
                            else json.loads(p)["datetime_from"]["utc"]
                        )
                    ),
                    "value": dfm["value"].astype(float),
                    "parameter": dfm["parameter"].apply(
                        lambda p: p.get("name") if isinstance(p, dict) else getattr(p, "name", None)
                    ),
                    "unit": dfm["parameter"].apply(
                        lambda p: (
                            p.get("units") if isinstance(p, dict) else getattr(p, "units", None)
                        )
                    ),
                    "data_source": dfm.get(
                        "source", pd.Series("openaq_v3", index=dfm.index)
                    ).fillna("openaq_v3"),
                }
            )
            .sort_values("timestamp_utc")
            .reset_index(drop=True)
        )
        return tidy

    @staticmethod
    def normalize_measurement_records(records: list[Any]) -> list[dict[str, Any]]:
        """Return a homogeneous mapping sequence suitable for pandas."""
        return [_measurement_mapping(record) for record in records]

    def run(
        self,
        output_csv: Optional[str] = None,
        raw_output: bool = False,
        skip_confirm: bool = False,
    ) -> pd.DataFrame:
        """
        Execute static mode analysis.

        Args:
            output_csv: Optional output CSV path for summary
            raw_output: Whether to save raw measurement data to CSV files

        Returns:
            Summary DataFrame with aggregate metrics per subject

        Note:
            To access raw hourly or daily data, use get_raw_data() or get_daily_data()
            methods after calling run().
        """
        try:
            self.read_and_validate_input()
            calls, est_min, est_hr = self.estimate_api_calls()
            workload_msg = (
                f"Projected workload - {calls} OpenAQ calls "
                f"(≈ {est_min:.1f} min | {est_hr:.2f} hr under free-tier limits)"
            )
            logger.info(workload_msg)
            # Also print to ensure visibility even if logging isn't configured
            print(f"\n{workload_msg}")

            if not skip_confirm and not prompt_user("Shall we proceed?"):
                logger.warning("Run aborted by user.")
                return pd.DataFrame()

            pol_label = ", ".join(p.upper() for p in self.pollutants)
            logger.info("Starting data collection for %s via OpenAQ", pol_label)
            results = self._run_static(raw_output)
            df_out = pd.DataFrame(results)

            if df_out.empty:
                logger.warning("Run finished - no usable data collected.")
                return df_out

            # Generate plots
            df_out = self.plotter.plot_distance_qc(df_out, self.distance_threshold_km)
            self.plotter.plot_daily_heatmaps(self._per_subject_tidy)

            # Print summary
            pd.set_option("display.max_columns", None, "display.width", None)
            pol_display = (
                "all pollutants" if self.pollutant == "all" else pretty_pollutant(self.pollutant)
            )
            print(f"\nExposure-metric summary (OpenAQ · STATIC · {pol_display}):\n")
            print(df_out.to_string(index=False, float_format="%.3f"), "\n")

            if output_csv:
                df_out.to_csv(output_csv, index=False)
                logger.info("Summary written → %s", output_csv)

            logger.info(
                "All done - %d participant rows processed with %d OpenAQ calls.",
                len(df_out),
                self.client.total_calls,
            )
            return df_out

        except Exception as e:  # Boundary catch-all: top-level run() must not propagate
            logger.error("Fatal error - %s", e)
            return pd.DataFrame()

    def _use_catalog(self) -> bool:
        """Return whether a country-level location catalog is appropriate."""
        if self.df_input is None or len(self.pollutants) != 1:
            return False
        if self.location_strategy == "per_subject":
            return False
        if len(self.country) != 2:
            return False
        return self.location_strategy == "catalog" or len(self.df_input) >= self.catalog_min_subjects

    @staticmethod
    def _coordinates(location: Any) -> tuple[float | None, float | None]:
        coordinates = getattr(location, "coordinates", None)
        if coordinates is None and isinstance(location, dict):
            coordinates = location.get("coordinates")
        if isinstance(coordinates, dict):
            return coordinates.get("latitude"), coordinates.get("longitude")
        return getattr(coordinates, "latitude", None), getattr(coordinates, "longitude", None)

    def _geocode_row(self, row: Any) -> tuple[float, float]:
        """Resolve a cohort row and retain successful geocodes in the run cache."""
        zip_code = getattr(row, "zip", None)
        if pd.notna(zip_code):
            cache_key = {"kind": "geocode_zip", "country": self.country, "lookup": str(zip_code)}
            resolver = lambda: geocode_zip(str(zip_code), country=self.country)
        else:
            address = str(getattr(row, "address"))
            cache_key = {"kind": "geocode_address", "lookup": address}
            resolver = lambda: geocode_address(address)

        if self.cache:
            cached = self.cache.get(**cache_key)
            if cached is not None:
                return float(cached[0]), float(cached[1])

        coordinates = resolver()
        if self.cache:
            self.cache.put(list(coordinates), **cache_key)
        return coordinates

    @staticmethod
    def _sensor_parameter(sensor: Any) -> str:
        parameter = getattr(sensor, "parameter", None)
        if parameter is None and isinstance(sensor, dict):
            parameter = sensor.get("parameter")
        if isinstance(parameter, dict):
            return str(parameter.get("name", "")).lower()
        return str(getattr(parameter, "name", "")).lower()

    def _load_location_catalog(self) -> list[Any] | None:
        """Cache a complete country catalog for local station selection.

        This avoids one nearby-location request per participant. It is only used
        after a bounded complete fetch; a truncated catalog always falls back to
        direct OpenAQ location discovery.
        """
        if not self._use_catalog():
            return None
        cache_key = {
            "endpoint": "country_location_catalog",
            "iso": self.country.upper(),
            "pollutants": self.pollutants,
        }
        locations = self.cache.get(**cache_key) if self.cache else None
        if locations is not None:
            self._catalog_used = True
            return locations

        locations = []
        page = 1
        max_locations = 10_000
        while len(locations) < max_locations:
            response = self.client.list_locations(
                iso=self.country.upper(), limit=1_000, page=page
            )
            batch = list(response.results or [])
            locations.extend(batch)
            if len(batch) < 1_000:
                if self.cache:
                    self.cache.put(locations, **cache_key)
                self._catalog_used = True
                logger.info(
                    "Loaded %d OpenAQ locations for local %s catalog selection.",
                    len(locations),
                    self.country.upper(),
                )
                return locations
            page += 1

        logger.warning(
            "OpenAQ country catalog reached the %d-location safety cap; using per-subject discovery.",
            max_locations,
        )
        return None

    def _catalog_stations(
        self, lat: float, lon: float, start_dt=None, end_dt=None
    ) -> list[Any]:
        """Select compatible catalog locations within the approved search radius."""
        if not self._catalog_locations:
            return []
        candidates = []
        for location in self._catalog_locations:
            station_lat, station_lon = self._coordinates(location)
            if station_lat is None or station_lon is None:
                continue
            if not any(self._sensor_parameter(sensor) in self.pollutants for sensor in location.sensors or []):
                continue
            if start_dt is not None and end_dt is not None:
                first = _as_utc_timestamp(
                    _record_value(location, "datetime_first")
                    or _record_value(location, "datetimeFirst")
                )
                last = _as_utc_timestamp(
                    _record_value(location, "datetime_last")
                    or _record_value(location, "datetimeLast")
                )
                start = _as_utc_timestamp(start_dt)
                end = _as_utc_timestamp(end_dt)
                if ((first is not None and end is not None and first >= end)
                        or (last is not None and start is not None and last < start)):
                    continue
            distance = haversine(lat, lon, float(station_lat), float(station_lon))
            if distance <= self.search_radius_m:
                candidates.append((distance, location))
        return [location for _, location in sorted(candidates, key=lambda item: item[0])]

    def _nearby_stations(self, lat: float, lon: float, start_dt=None, end_dt=None) -> list[Any]:
        """Find stations by cached catalog or by the canonical OpenAQ point query."""
        catalog_stations = self._catalog_stations(lat, lon, start_dt, end_dt)
        if self._catalog_used:
            return catalog_stations

        # OpenAQ point queries reject radii above 25 km. Larger, contract-locked
        # searches require the complete country catalog and local distance filtering.
        if self.search_radius_m > 25_000:
            raise ConfigurationError(
                "search_radius_km above 25 requires a complete country location catalog."
            )

        cache_key = dict(
            endpoint="list_locations", lat=lat, lon=lon, radius=self.search_radius_m
        )
        cached_stations = self.cache.get(**cache_key) if self.cache else None
        if cached_stations is not None:
            return cached_stations
        stations = self.client.list_locations(
            coordinates=(lat, lon), radius=self.search_radius_m, limit=self.config.station_limit
        ).results
        if self.cache:
            self.cache.put(stations, **cache_key)
        return stations

    def _fetch_sensor_data(
        self,
        sensor_id: int,
        location_id: int,
        parameter: str,
        start_dt,
        end_dt,
        start_iso: str,
        end_iso: str,
    ):
        """Fetch one sensor's chosen temporal resolution once per session/cache key."""
        key = (sensor_id, start_iso, end_iso, self.temporal_resolution)
        if key in self._measurement_memory:
            return self._measurement_memory[key]
        cache_key = dict(
            endpoint=(
                "sensor_days_v3" if self.temporal_resolution == "daily" else "sensor_hours_v3"
            ),
            sensor_id=sensor_id,
            datetime_from=start_iso,
            datetime_to=end_iso,
            data=self.temporal_resolution,
        )
        rows = self.cache.get(**cache_key) if self.cache else None
        if rows is None:
            rows = []
            page = 1
            while True:
                if self.temporal_resolution == "daily":
                    response = self.client.list_daily_measurements(
                        sensor_id=sensor_id,
                        date_from=start_dt.date().isoformat(),
                        date_to=(end_dt - timedelta(days=1)).date().isoformat(),
                        limit=1_000,
                        page=page,
                    )
                else:
                    response = self.client.list_measurements(
                        sensors_id=sensor_id,
                        data="hours",
                        datetime_from=start_dt,
                        datetime_to=end_dt,
                        limit=1_000,
                        page=page,
                    )
                batch = list(response.results or [])
                if not batch:
                    break
                rows.extend(batch)
                if len(batch) < 1_000:
                    break
                page += 1
            if self.cache:
                self.cache.put(rows, **cache_key)
        if not rows:
            rows = self._fetch_archive_daily_range(location_id, parameter, start_dt, end_dt)
        elif self.temporal_resolution == "daily":
            v3_dates = _measurement_dates(rows)
            expected_days = (end_dt.date() - start_dt.date()).days
            if len(v3_dates) < expected_days:
                archive_rows = self._fetch_archive_daily_range(
                    location_id, parameter, start_dt, end_dt
                )
                if archive_rows:
                    rows = self.normalize_measurement_records(rows)
                    rows.extend(row for row in archive_rows if _measurement_date(row) not in v3_dates)
        self._measurement_memory[key] = rows
        return rows

    def _fetch_archive_daily_range(self, location_id: int, parameter: str, start_dt, end_dt):
        """Recover a bounded historical series or plan a larger S3 retrieval."""
        if not self.config.archive_fallback_enabled:
            return []
        start_date = start_dt.date()
        end_date = (end_dt - timedelta(days=1)).date()
        dates_key = {
            "endpoint": "location_archive_available_dates_v1",
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
            return []
        rows = self.archive_client.fetch_daily_range_checkpointed(
            location_id,
            parameter=parameter,
            available_dates=available_dates,
            chunk_size=self.config.archive_fallback_max_objects,
            cache=self.cache,
        )
        if self.archive_client.last_errors:
            logger.warning(
                "Archive fallback recovered a partial %s series for location %s; %d "
                "location-day objects remain retryable.",
                parameter, location_id, len(self.archive_client.last_errors),
            )
        if rows:
            logger.info(
                "Recovered %d daily %s values from the OpenAQ S3 archive for location %s.",
                len(rows),
                parameter,
                location_id,
            )
        return rows

    def _run_static(self, raw_output: bool) -> list[dict]:
        """Core static processing loop."""
        logger.info("Entering STATIC mode - one row per participant")
        raw_dir = (self.output_dir or Path.cwd()) / "raw_static"
        if raw_output:
            raw_dir.mkdir(parents=True, exist_ok=True)

        results: list[dict] = []
        total = len(self.df_input)
        self._catalog_locations = self._load_location_catalog()

        for idx, row in enumerate(
            tqdm(self.df_input.itertuples(), total=total, desc="Subjects", unit="subj"), 1
        ):
            sid = row.subject_id
            logger.debug("Processing subject %s (%d of %d total)", sid, idx, total)

            # Get subject location (coordinates or geocode)
            try:
                # Check if coordinates are provided directly
                if hasattr(row, "latitude") and hasattr(row, "longitude"):
                    lat_val = getattr(row, "latitude", None)
                    lon_val = getattr(row, "longitude", None)
                    if pd.notna(lat_val) and pd.notna(lon_val):
                        lat = float(lat_val)
                        lon = float(lon_val)
                        logger.debug(
                            "Using provided coordinates for subject %s: (%.4f, %.4f)", sid, lat, lon
                        )
                    else:
                        # Coordinates are missing, fall back to geocoding
                        lat, lon = self._geocode_row(row)
                        logger.debug(
                            "Geocoded location for subject %s: (%.4f, %.4f)", sid, lat, lon
                        )
                else:
                    # No coordinates provided, use geocoding
                    lat, lon = self._geocode_row(row)
                    logger.debug("Geocoded location for subject %s: (%.4f, %.4f)", sid, lat, lon)
            except GeocodingError as e:
                logger.warning("%s - skipped.", e)
                continue
            except (ValueError, TypeError) as e:
                logger.warning("Invalid coordinates for subject %s: %s - skipped.", sid, e)
                continue

            # The OpenAQ client accepts datetime objects. Passing ISO strings
            # ending in Z breaks in openaq's Python 3.10 validator, which
            # validates the suffix but later parses the original string.
            start_dt = row.start_dt.to_pydatetime()
            end_dt = (row.end_dt + timedelta(days=1)).to_pydatetime()
            start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

            stations = self._nearby_stations(lat, lon, start_dt, end_dt)

            if not stations:
                logger.warning(
                    "No stations within %dm for subject %s.", self.search_radius_m, sid
                )
                for cur_pol in self.pollutants:
                    results.append({
                        "subject_id": sid,
                        "pollutant": cur_pol,
                        "mean": None,
                        "qc_flag": "NO_STATIONS",
                        "search_radius_km": self.search_radius_m / 1000,
                        "n_stations_screened": 0,
                        "n_stations_rejected_incomplete": 0,
                    })
                continue

            # Loop over requested pollutants (shared station discovery)
            expected_hours = (row.end_dt - row.start_dt).days * 24 + 24
            expected_samples = (
                expected_hours if self.temporal_resolution == "hourly" else expected_hours // 24
            )
            for cur_pol in self.pollutants:
                # Collect data from up to n_stations for IDW averaging
                station_data = []  # list of (metrics, distance_m, station_info, tidy_df, dfm, sensor)
                stations_screened = 0
                rejected_incomplete: list[dict[str, Any]] = []

                for loc in stations:
                    if len(station_data) >= self.n_stations:
                        break
                    for sensor in loc.sensors or []:
                        if getattr(sensor.parameter, "name", "").lower() != cur_pol:
                            continue

                        meas_rows = self._fetch_sensor_data(
                            sensor.id, loc.id, cur_pol, start_dt, end_dt, start_iso, end_iso
                        )

                        if not meas_rows:
                            break

                        dfm = pd.DataFrame(meas_rows)
                        tidy = self._tidy_raw_df(dfm)
                        self._per_subject_tidy.setdefault(str(sid), []).append(tidy)

                        if raw_output:
                            fname = (
                                raw_dir / f"{sid}_{pretty_pollutant(cur_pol)}_"
                                f"{row.start_dt:%Y%m%d}-{row.end_dt:%Y%m%d}_{loc.id}.csv"
                            )
                            tidy.to_csv(fname, index=False)
                            logger.info("Raw file saved → %s", fname)

                        coords = loc.coordinates
                        st_lat = (
                            coords.get("latitude") if isinstance(coords, dict) else coords.latitude
                        )
                        st_lon = (
                            coords.get("longitude")
                            if isinstance(coords, dict)
                            else coords.longitude
                        )
                        dist_m = haversine(lat, lon, st_lat, st_lon)

                        # Station metadata
                        st_name = (
                            loc.name
                            if hasattr(loc, "name")
                            else (loc.get("name") if isinstance(loc, dict) else None)
                        )
                        st_id = (
                            loc.id
                            if hasattr(loc, "id")
                            else (loc.get("id") if isinstance(loc, dict) else None)
                        )

                        metrics = calculate_metrics(
                            dfm,
                            cur_pol,
                            threshold=getattr(self, "threshold", None),
                            expected_hours=expected_samples,
                            outlier_detection=self.outlier_detection,
                        )

                        stations_screened += 1
                        completeness = metrics.get("completeness_pct")
                        if (
                            self.min_completeness is not None
                            and completeness is not None
                            and float(completeness) < float(self.min_completeness)
                        ):
                            rejected_incomplete.append({
                                "station_id": st_id,
                                "distance_m": dist_m,
                                "completeness_pct": completeness,
                            })
                            continue

                        station_data.append(
                            {
                                "metrics": metrics,
                                "distance_m": dist_m,
                                "st_lat": st_lat,
                                "st_lon": st_lon,
                                "st_name": st_name,
                                "st_id": st_id,
                                "unit": self._extract_unit(dfm, sensor),
                                "tidy": tidy,
                                "data_source": ";".join(sorted(tidy["data_source"].dropna().unique())),
                            }
                        )
                        break  # Only one sensor per station per pollutant

                if not station_data:
                    results.append({
                        "subject_id": sid,
                        "pollutant": cur_pol,
                        "mean": None,
                        "qc_flag": (
                            "NO_COMPLETE_STATION" if rejected_incomplete else "NO_OBSERVATIONS"
                        ),
                        "search_radius_km": self.search_radius_m / 1000,
                        "n_stations_screened": stations_screened,
                        "n_stations_rejected_incomplete": len(rejected_incomplete),
                        "nearest_rejected_station_id": (
                            rejected_incomplete[0]["station_id"] if rejected_incomplete else None
                        ),
                        "nearest_rejected_distance_m": (
                            rejected_incomplete[0]["distance_m"] if rejected_incomplete else None
                        ),
                        "nearest_rejected_completeness_pct": (
                            rejected_incomplete[0]["completeness_pct"]
                            if rejected_incomplete else None
                        ),
                    })
                    continue

                idw_requested = self.n_stations > 1
                primary = station_data[0]
                if idw_requested and len(station_data) > 1:
                    idw_df = idw_hourly_series(
                        [s["tidy"] for s in station_data],
                        [s["distance_m"] for s in station_data],
                        pollutant=cur_pol,
                        outlier_detection=self.outlier_detection,
                    )
                    if idw_df.empty:
                        continue
                    self._per_subject_idw.setdefault(str(sid), []).append(idw_df)
                    m = calculate_metrics(
                        idw_df,
                        cur_pol,
                        threshold=getattr(self, "threshold", None),
                        expected_hours=expected_samples,
                        outlier_detection=False,
                    )
                    station_ids = ";".join(str(s["st_id"]) for s in station_data if s["st_id"])
                    station_names = ";".join(str(s["st_name"]) for s in station_data if s["st_name"])
                    row_dict = {
                        "subject_id": sid,
                        "pollutant": cur_pol,
                        "mean": m["mean"],
                        "std": m["std"],
                        "median": m["median"],
                        "min": m["min"],
                        "max": m["max"],
                        "n_samples": m["n_samples"],
                        "unit": primary["unit"],
                        "station_id": station_ids,
                        "station_name": station_names,
                        "station_latitude": primary["st_lat"],
                        "station_longitude": primary["st_lon"],
                        "distance_m": primary["distance_m"],
                        "n_stations_idw": len(station_data),
                        "n_stations_used": len(station_data),
                        "temporal_resolution": self.temporal_resolution,
                        "location_strategy": "catalog" if self._catalog_used else "per_subject",
                        "search_radius_km": self.search_radius_m / 1000,
                        "n_stations_screened": stations_screened,
                        "n_stations_rejected_incomplete": len(rejected_incomplete),
                        "data_source": ";".join(sorted({s["data_source"] for s in station_data if s["data_source"]})),
                    }
                else:
                    s = primary
                    m = s["metrics"]
                    if idw_requested:
                        self._per_subject_idw.setdefault(str(sid), []).append(s["tidy"])
                    row_dict = {
                        "subject_id": sid,
                        "pollutant": cur_pol,
                        "mean": m["mean"],
                        "std": m["std"],
                        "median": m["median"],
                        "min": m["min"],
                        "max": m["max"],
                        "n_samples": m["n_samples"],
                        "unit": s["unit"],
                        "station_id": s["st_id"],
                        "station_name": s["st_name"],
                        "station_latitude": s["st_lat"],
                        "station_longitude": s["st_lon"],
                        "distance_m": s["distance_m"],
                        "n_stations_idw": 1 if idw_requested else None,
                        "n_stations_used": 1 if idw_requested else None,
                        "temporal_resolution": self.temporal_resolution,
                        "location_strategy": "catalog" if self._catalog_used else "per_subject",
                        "search_radius_km": self.search_radius_m / 1000,
                        "n_stations_screened": stations_screened,
                        "n_stations_rejected_incomplete": len(rejected_incomplete),
                        "data_source": s["data_source"],
                    }

                aqi_val, aqi_cat = None, None
                if m["mean"] is not None:
                    with contextlib.suppress(ValueError):
                        aqi_val, aqi_cat = concentration_to_aqi(m["mean"], cur_pol)
                row_dict["aqi"] = aqi_val
                row_dict["aqi_category"] = aqi_cat

                if "time_weighted_mean" in m:
                    row_dict["time_weighted_mean"] = m["time_weighted_mean"]
                if "n_outliers_removed" in m:
                    row_dict["n_outliers_removed"] = m["n_outliers_removed"]
                if "exceedance_count" in m:
                    row_dict["exceedance_count"] = m["exceedance_count"]
                    row_dict["exceedance_pct"] = m["exceedance_pct"]
                    row_dict["exceedance_threshold"] = m["exceedance_threshold"]
                if "completeness_pct" in m:
                    row_dict["completeness_pct"] = m["completeness_pct"]
                    if self.min_completeness is not None:
                        row_dict["qc_flag"] = (
                            "PASS"
                            if m["completeness_pct"] >= self.min_completeness
                            else "FAIL"
                        )
                results.append(row_dict)

        return results

    @staticmethod
    def _extract_unit(dfm: pd.DataFrame, sensor) -> Optional[str]:
        """Extract unit information from measurement data or sensor."""
        if "unit" in dfm.columns and not dfm["unit"].isna().all():
            return dfm["unit"].dropna().iloc[0]
        units_attr = getattr(getattr(sensor, "parameter", None), "units", None)
        if units_attr:
            return units_attr[0] if isinstance(units_attr, list) else units_attr
        return None

    def get_raw_data(self, subject_id: Optional[str] = None) -> pd.DataFrame:
        """
        Get raw hourly measurement data.

        Args:
            subject_id: Optional subject ID to filter. If None, returns all subjects.

        Returns:
            DataFrame with columns: subject_id, timestamp_utc, value, parameter, unit

        Raises:
            RuntimeError: If run() hasn't been called yet.
        """
        if not hasattr(self, "_per_subject_tidy") or not self._per_subject_tidy:
            raise RuntimeError("Must call run() first to collect data.")

        all_data = []
        for sid, frames in self._per_subject_tidy.items():
            if subject_id is not None and str(sid) != str(subject_id):
                continue
            for df in frames:
                df_with_id = df.copy()
                df_with_id["subject_id"] = str(sid)
                all_data.append(df_with_id)

        if not all_data:
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)
        combined["timestamp_utc"] = pd.to_datetime(combined["timestamp_utc"], utc=True)
        return combined.sort_values(["subject_id", "timestamp_utc"]).reset_index(drop=True)

    def get_daily_data(
        self, subject_id: Optional[str] = None, agg_functions: Optional[list[str]] = None
    ) -> pd.DataFrame:
        """
        Get daily aggregated pollutant data.

        Args:
            subject_id: Optional subject ID to filter. If None, returns all subjects.
            agg_functions: Aggregation functions to compute. Default: ['mean', 'min', 'max', 'count']

        Returns:
            DataFrame with columns: subject_id, date, parameter, and one column per aggregation function

        Raises:
            RuntimeError: If run() hasn't been called yet.
        """
        if agg_functions is None:
            agg_functions = ["mean", "min", "max", "count"]
        raw = self.get_raw_data(subject_id)
        if self.n_stations > 1 and self._per_subject_idw:
            frames = []
            for sid, subject_frames in self._per_subject_idw.items():
                if subject_id is not None and str(sid) != str(subject_id):
                    continue
                for frame in subject_frames:
                    series = frame.copy()
                    series["subject_id"] = str(sid)
                    frames.append(series)
            if frames:
                raw = pd.concat(frames, ignore_index=True)
        if raw.empty:
            return pd.DataFrame()

        raw["date"] = raw["timestamp_utc"].dt.date
        daily = (
            raw.groupby(["subject_id", "date", "parameter"])["value"]
            .agg(agg_functions)
            .reset_index()
        )
        daily.columns = ["subject_id", "date", "parameter", *agg_functions]

        return daily.sort_values(["subject_id", "date"]).reset_index(drop=True)

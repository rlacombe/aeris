"""
Dynamic mode estimator classes for exposure estimation.
"""

import contextlib
import logging
import sys
import warnings
from datetime import timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests
from tqdm import tqdm

from ..api_clients import (
    GoogleAirQualityClient,
    OpenMeteoClient,
    OverpassClient,
    PurpleAirClient,
    RateLimitedOpenAQ,
)
from ..config import ALLOWED_POLLUTANTS, Config
from ..exceptions import ConfigurationError
from ..plotting import DynamicPlotter
from ..utils import calculate_metrics, concentration_to_aqi, prompt_user
from ..validators import validate_dynamic_input

logger = logging.getLogger(__name__)

# Silence pandas FutureWarning about downcasting in replace to keep console clean for users
warnings.filterwarnings(
    "ignore",
    category=FutureWarning,
    message=r".*Downcasting behavior in `replace` is deprecated.*",
)


class ExposureEstimatorGoogleMapsDynamic:
    """
    Dynamic mode estimator using Google Maps Air Quality API.

    Processes a single subject with 24 hourly GPS points,
    fetching concentrations for all six pollutants.
    """

    def __init__(
        self,
        input_csv: str,
        gmaps_api_key: Optional[str] = None,
        config: Optional[Config] = None,
        min_completeness: Optional[float] = None,
        cache=None,
        output_dir: Optional[str] = None,
    ) -> None:
        # Auto-configure logging if not already configured
        root_logger = logging.getLogger()
        if not root_logger.handlers:
            logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

        logger.info("Initialising ExposureEstimator (Google Maps Air Quality · DYNAMIC)")

        self.input_csv = input_csv

        # Configuration
        self.config = config or Config.from_env()
        if gmaps_api_key:
            self.config.google_maps_api_key = gmaps_api_key

        if not self.config.google_maps_api_key:
            raise ConfigurationError(
                "Missing Google Maps Air Quality API key (flag or GOOGLE_MAPS_AIR_QUALITY_API_KEY env var)."
            )

        self.output_dir = Path(output_dir) if output_dir else None
        if self.output_dir is not None:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize API client and plotter
        self.client = GoogleAirQualityClient(api_key=self.config.google_maps_api_key)
        self.plotter = DynamicPlotter(output_dir=self.output_dir)

        self.min_completeness = min_completeness
        self.cache = cache

        # Data storage
        self.df_input: Optional[pd.DataFrame] = None

    def read_and_validate_input(self) -> None:
        """Load and validate dynamic CSV input."""
        logger.info("Reading CSV: %s", self.input_csv)
        p = Path(self.input_csv)
        if not p.exists():
            raise ConfigurationError(f"CSV file not found: {self.input_csv}")

        df = pd.read_csv(p, dtype=str)
        self.df_input = validate_dynamic_input(df)
        subjects = self.df_input["subject_id"].unique()
        logger.info(
            "Mode locked: DYNAMIC (Google Maps Air Quality API) · %d subject(s): %s",
            len(subjects),
            ", ".join(str(s) for s in subjects[:5]),
        )

    def estimate_api_calls(self) -> tuple[int, float, float]:
        """Estimate number of API calls needed."""
        if self.df_input is None:
            raise RuntimeError("read_and_validate_input() must be called first")
        calls = len(self.df_input)
        return calls, 0.0, 0.0

    @staticmethod
    def _map_unit(unit_enum: Optional[str]) -> Optional[str]:
        """Map Google unit enums to human-readable labels."""
        if unit_enum == "MICROGRAMS_PER_CUBIC_METER":
            return "µg/m³"
        if unit_enum == "PARTS_PER_BILLION":
            return "ppb"
        if unit_enum == "PARTS_PER_MILLION":
            return "ppm"
        return None

    def run(
        self,
        output_csv: Optional[str] = None,
        raw_output: bool = False,
        skip_confirm: bool = False,
    ) -> pd.DataFrame:
        """
        Execute dynamic mode analysis.

        Args:
            output_csv: Optional output CSV path
            raw_output: Whether to save raw measurement data
            skip_confirm: Skip interactive confirmation prompt

        Returns:
            Summary DataFrame
        """
        try:
            self.read_and_validate_input()
            calls, _, _ = self.estimate_api_calls()
            workload_msg = f"Projected workload - {calls} Google Air Quality calls"
            logger.info(workload_msg)
            # Also print to ensure visibility even if logging isn't configured
            print(f"\n{workload_msg}")

            if not skip_confirm and not prompt_user("Shall we proceed?"):
                logger.warning("Run aborted by user.")
                return pd.DataFrame()

            logger.info("Starting data collection for all pollutants via Google Maps Air Quality")

            df = self.df_input
            assert df is not None

            raw_dir = Path.cwd() / "raw_gps_gmaps"
            if raw_output:
                raw_dir.mkdir(parents=True, exist_ok=True)

            # Accumulators across all subjects (for plots)
            all_tidy_by_pol: dict[str, list[pd.DataFrame]] = {p: [] for p in ALLOWED_POLLUTANTS}
            all_units_seen: dict[str, list[str]] = {p: [] for p in ALLOWED_POLLUTANTS}
            all_allpol_rows: list[dict] = []
            all_summary_rows: list[dict] = []

            subjects = df.groupby("subject_id", sort=False)
            for sid, subj_df in tqdm(subjects, desc="Subjects", unit="subj"):
                tidy_by_pol: dict[str, list[pd.DataFrame]] = {p: [] for p in ALLOWED_POLLUTANTS}
                units_seen: dict[str, list[str]] = {p: [] for p in ALLOWED_POLLUTANTS}
                allpol_rows: list[dict] = []

                for row in tqdm(
                    subj_df.itertuples(),
                    total=len(subj_df),
                    desc=f"  GPS [{sid}]",
                    unit="pt",
                    leave=False,
                ):
                    lat, lon, dt = float(row.latitude), float(row.longitude), row.dt
                    dt_floor = pd.Timestamp(dt).floor("h")
                    start_iso = dt_floor.strftime("%Y-%m-%dT%H:%M:%SZ")
                    end_iso = (dt_floor + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

                    cache_key = dict(
                        endpoint="history_lookup",
                        lat=lat,
                        lon=lon,
                        start_iso=start_iso,
                        end_iso=end_iso,
                    )
                    cached = self.cache.get(**cache_key) if self.cache else None
                    if cached is not None:
                        resp = cached
                    else:
                        resp = self.client.history_lookup(
                            lat,
                            lon,
                            start_iso=start_iso,
                            end_iso=end_iso,
                            extra_computations=["POLLUTANT_CONCENTRATION"],
                            page_size=1,
                        )
                        if self.cache:
                            self.cache.put(resp, **cache_key)

                    hours = (
                        resp.get("hoursInfo")
                        or resp.get("hours")
                        or resp.get("hourlyReports")
                        or []
                    )
                    if not hours:
                        logger.debug(
                            "Empty hour %s-%s @ (%.4f, %.4f)", start_iso, end_iso, lat, lon
                        )
                        continue

                    hi = hours[0]
                    pols = hi.get("pollutants", []) or []
                    if not pols:
                        continue

                    ts_utc = pd.to_datetime(hi.get("dateTime"), utc=True, errors="coerce")

                    row_out: dict[str, Any] = {
                        "timestamp_utc": ts_utc,
                        "latitude": lat,
                        "longitude": lon,
                    }

                    for p in pols:
                        code = str(p.get("code", "")).lower()
                        if code not in ALLOWED_POLLUTANTS:
                            continue
                        conc = p.get("concentration") or {}
                        val = conc.get("value")
                        unit_lbl = self._map_unit(conc.get("units"))
                        if val is None:
                            continue

                        units_seen[code].append(unit_lbl or "n/a")
                        row_out[code] = val
                        tidy_by_pol[code].append(
                            pd.DataFrame(
                                {
                                    "timestamp_utc": [ts_utc],
                                    "value": [val],
                                    "parameter": [code],
                                    "unit": [unit_lbl],
                                    "latitude": [lat],
                                    "longitude": [lon],
                                }
                            )
                        )

                    allpol_rows.append(row_out)

                    if raw_output:
                        lat_s = f"{lat:.5f}".replace(".", "p")
                        lon_s = f"{lon:.5f}".replace(".", "p")
                        fname = (
                            raw_dir / f"{sid}_allpollutants_{dt:%Y%m%dT%H%M%SZ}_{lat_s}_{lon_s}.csv"
                        )
                        pd.DataFrame([row_out]).to_csv(fname, index=False)

                # Build summary for this subject
                expected_hours = len(subj_df)
                for pol in ALLOWED_POLLUTANTS:
                    if not tidy_by_pol[pol]:
                        continue
                    df_pol = pd.concat(tidy_by_pol[pol], ignore_index=True)
                    m = calculate_metrics(
                        df_pol[["timestamp_utc", "value", "parameter", "unit"]],
                        pol,
                        threshold=getattr(self, "threshold", None),
                        expected_hours=expected_hours,
                    )
                    unit_vals = [u for u in units_seen[pol] if u and u != "n/a"]
                    unit_final = max(set(unit_vals), key=unit_vals.count) if unit_vals else None

                    aqi_val, aqi_cat = None, None
                    if m["mean"] is not None:
                        with contextlib.suppress(ValueError):
                            aqi_val, aqi_cat = concentration_to_aqi(m["mean"], pol)

                    row_dict = {
                        "subject_id": sid,
                        "pollutant": pol,
                        "mean": m["mean"],
                        "std": m["std"],
                        "median": m["median"],
                        "min": m["min"],
                        "max": m["max"],
                        "n_samples": m["n_samples"],
                        "aqi": aqi_val,
                        "aqi_category": aqi_cat,
                        "unit": unit_final,
                    }
                    if "exceedance_count" in m:
                        row_dict["exceedance_count"] = m["exceedance_count"]
                        row_dict["exceedance_pct"] = m["exceedance_pct"]
                        row_dict["exceedance_threshold"] = m["exceedance_threshold"]
                    if "completeness_pct" in m:
                        row_dict["completeness_pct"] = m["completeness_pct"]
                        if self.min_completeness is not None:
                            row_dict["qc_flag"] = (
                                "PASS" if m["completeness_pct"] >= self.min_completeness else "FAIL"
                            )
                    all_summary_rows.append(row_dict)

                # Accumulate for plots
                for p in ALLOWED_POLLUTANTS:
                    all_tidy_by_pol[p].extend(tidy_by_pol[p])
                    all_units_seen[p].extend(units_seen[p])
                all_allpol_rows.extend(allpol_rows)

            df_out = (
                pd.DataFrame(all_summary_rows).sort_values(["subject_id", "pollutant"])
                if all_summary_rows
                else pd.DataFrame()
            )

            # Print summary
            pd.set_option("display.max_columns", None, "display.width", None)
            print("\nExposure-metric summary (Google AQ · DYNAMIC · all pollutants):\n")
            if df_out.empty:
                logger.warning("No summary metrics (no pollutant rows).")
            else:
                print(df_out.to_string(index=False, float_format="%.3f"), "\n")

            if output_csv and not df_out.empty:
                df_out.to_csv(output_csv, index=False)
                logger.info("Summary written → %s", output_csv)

            # Generate plots
            self._generate_route_plots(all_tidy_by_pol, all_units_seen)
            self._generate_boxplots(all_allpol_rows, all_units_seen)

            n_subjects = df["subject_id"].nunique()
            logger.info("All done - %d subject(s) processed with Google Air Quality.", n_subjects)
            return df_out

        except Exception as e:  # Boundary catch-all: top-level run() must not propagate
            logger.error("Fatal error - %s", e)
            return pd.DataFrame()

    def _generate_route_plots(
        self, tidy_by_pol: dict[str, list[pd.DataFrame]], units_seen: dict[str, list[str]]
    ) -> None:
        """Generate route plots for all pollutants."""
        for pol in ALLOWED_POLLUTANTS:
            if not tidy_by_pol[pol]:
                continue
            df_route = pd.concat(tidy_by_pol[pol], ignore_index=True).sort_values("timestamp_utc")
            df_route = df_route.drop_duplicates(subset=["timestamp_utc"])
            df_route = df_route[["timestamp_utc", "latitude", "longitude", "value"]].rename(
                columns={"value": pol}
            )
            unit_vals = [u for u in units_seen[pol] if u and u != "n/a"]
            unit_final = max(set(unit_vals), key=unit_vals.count) if unit_vals else None
            self.plotter.plot_route_map(df_route, pol, unit_final)

    def _generate_boxplots(self, allpol_rows: list[dict], units_seen: dict[str, list[str]]) -> None:
        """Generate boxplots for all pollutants."""
        if allpol_rows:
            df_all = pd.DataFrame(allpol_rows)
            df_all["timestamp_utc"] = pd.to_datetime(
                df_all["timestamp_utc"], utc=True, errors="coerce"
            )
            units_map = {
                p: (max(set(us), key=us.count) if us else None) for p, us in units_seen.items()
            }
            self.plotter.plot_boxplots(df_all, units_map)
        else:
            logger.warning("Skipping boxplots - no multi-pollutant rows captured.")


class ExposureEstimatorXGBDynamic:
    """
    Dynamic mode estimator using an XGBoost dispersion model to predict PM2.5.
    Predictors per GPS point:
      - re_pm25: nearest PurpleAir sensor PM2.5 reading (within 5km), with OpenAQ fallback
      - Meteorology: temperature, humidity, windspeed, winddirection, precipitation (Open-Meteo)
      - dist_hwy, dist_art: distance to nearest highway/arterial (Overpass)
      - Land use/cover: OS, WA, ISF, TC, EL (Google Earth Engine)
      - weekday: 1 for Mon-Fri, 0 for Sat/Sun

    When no PurpleAir PM2.5 monitors are found within 5km of the target coordinates,
    the system automatically queries OpenAQ for PM2.5 measurements within a 25km radius
    if an OpenAQ API key is provided. This ensures better coverage in areas with limited
    PurpleAir sensor density.
    """

    def __init__(
        self,
        input_csv: str,
        purpleair_api_key: Optional[str] = None,
        openaq_api_key: Optional[str] = None,
        model_path: Optional[str] = None,
        config: Optional[Config] = None,
        min_completeness: Optional[float] = None,
        cache=None,
        output_dir: Optional[str] = None,
    ) -> None:
        # Auto-configure logging if not already configured
        root_logger = logging.getLogger()
        if not root_logger.handlers:
            logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)

        logger.info("Initialising ExposureEstimator (XGBoost dispersion · DYNAMIC · PM2.5)")

        self.input_csv = input_csv
        self.min_completeness = min_completeness
        self.cache = cache
        self.output_dir = Path(output_dir) if output_dir else None
        if self.output_dir is not None:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or Config.from_env()
        if purpleair_api_key:
            self.config.purpleair_api_key = purpleair_api_key
        if openaq_api_key:
            self.config.openaq_api_key = openaq_api_key
        if model_path:
            self.config.xgb_model_path = model_path

        if not self.config.purpleair_api_key:
            raise ConfigurationError(
                "Missing PurpleAir API key (flag or PURPLEAIR_API_KEY env var)."
            )

        # Model path: required for XGB mode
        # If not provided, try common filenames in order of preference
        if not self.config.xgb_model_path:
            # Try standard filenames (prefer JSON format to avoid sklearn version issues)
            possible_paths = [
                Path.cwd()
                / "xgb_model.json",  # Preferred: XGBoost Booster format (avoids sklearn issues)
                Path.cwd() / "xgb_final.json",
                Path.cwd() / "xgb_model.joblib",  # Alternative: sklearn pipeline format
                Path.cwd() / "xgb_final.joblib",
                Path.cwd() / "xgb_final (3).joblib",  # Legacy filename
            ]
            for default_path in possible_paths:
                if default_path.exists():
                    self.config.xgb_model_path = str(default_path)
                    logger.info("Using default model file: %s", default_path)
                    break
            else:
                raise ConfigurationError(
                    "Missing XGBoost model path. Please set AERIS_EXPOSURE_XGB_MODEL_PATH environment variable "
                    "or pass --model_path argument. Supported formats: .joblib (sklearn pipeline) or .json (XGBoost Booster)"
                )

        # Auto-detect features.txt if using JSON model and no feature path provided
        if not self.config.xgb_feature_names_path:
            model_path_str = str(self.config.xgb_model_path or "")
            if model_path_str.lower().endswith(".json"):
                # Try to find features.txt in same directory as model or current directory
                possible_feature_paths = [
                    Path(self.config.xgb_model_path).parent / "features.txt"
                    if self.config.xgb_model_path
                    else None,
                    Path.cwd() / "features.txt",
                ]
                for feat_path in possible_feature_paths:
                    if feat_path and feat_path.exists():
                        self.config.xgb_feature_names_path = str(feat_path)
                        logger.info("Auto-detected feature order file: %s", feat_path)
                        break

        # Initialize clients and plotter
        self.pa = PurpleAirClient(self.config.purpleair_api_key)
        self.met = OpenMeteoClient()
        self.osm = OverpassClient()

        # Initialize OpenAQ client if API key is provided (for fallback when PurpleAir unavailable)
        self.openaq = None
        if self.config.openaq_api_key:
            self.openaq = RateLimitedOpenAQ(self.config.openaq_api_key, self.config)
            logger.info(
                "OpenAQ client initialized (will be used as fallback when no PurpleAir sensors within 5km, searches within 25km)"
            )
        else:
            logger.info("OpenAQ API key not provided - will only use PurpleAir for PM2.5 readings")

        # Google Earth Engine is the PRIMARY source for LULC variables (per collaborator requirements)
        self.gee = None
        try:
            from ..api_clients import GEEClient  # type: ignore

            self.gee = GEEClient()
            logger.info("LULC source: Google Earth Engine (primary)")
            logger.debug(
                "GEE configuration: buffer=%sm, scale=%sm",
                getattr(getattr(self.gee, "cfg", {}), "get", lambda *_: None)("buffer_m"),
                getattr(getattr(self.gee, "cfg", {}), "get", lambda *_: None)("scale_m"),
            )
        except (ImportError, RuntimeError) as e:
            logger.error("GEE initialization failed: %s", e)
            logger.error(
                "LULC variables will be None. Install earthengine-api and authenticate: `earthengine authenticate`"
            )
            raise ConfigurationError(
                "Google Earth Engine is required for LULC variables. "
                "Install with `pip install earthengine-api` and authenticate with `earthengine authenticate`"
            ) from e
        self.plotter = DynamicPlotter(output_dir=self.output_dir)

        # Data storage
        self.df_input: Optional[pd.DataFrame] = None
        self._model = None

    def read_and_validate_input(self) -> None:
        logger.info("Reading CSV: %s", self.input_csv)
        p = Path(self.input_csv)
        if not p.exists():
            raise ConfigurationError(f"CSV file not found: {self.input_csv}")
        df = pd.read_csv(p, dtype=str)
        self.df_input = validate_dynamic_input(df)
        subjects = self.df_input["subject_id"].unique()
        logger.info(
            "Mode locked: DYNAMIC (XGBoost dispersion) · %d subject(s): %s",
            len(subjects),
            ", ".join(str(s) for s in subjects[:5]),
        )

    def _load_model(self):
        if self._model is None:
            model_path = self.config.xgb_model_path
            if model_path and str(model_path).lower().endswith(".json"):
                # Load as Booster
                import xgboost as xgb

                logger.info("Loading XGBoost Booster from %s", model_path)
                booster = xgb.Booster()
                booster.load_model(model_path)
                self._model = booster
            else:
                import joblib
                from sklearn.compose import ColumnTransformer

                logger.info("Loading dispersion model from %s", model_path)
                model = joblib.load(model_path)

                # Fix sklearn version incompatibility: handle "passthrough" string in ColumnTransformer
                if hasattr(model, "named_steps"):
                    preproc = model.named_steps.get("preproc")
                    if isinstance(preproc, ColumnTransformer):
                        # Check if any transformer is the string "passthrough" (sklearn 0.23.2 format)
                        transformers_list = getattr(preproc, "transformers_", None) or getattr(
                            preproc, "transformers", []
                        )
                        has_passthrough_str = any(
                            isinstance(t[1], str) and t[1] == "passthrough"
                            for t in transformers_list
                        )

                        if has_passthrough_str:
                            logger.warning(
                                "Model contains 'passthrough' string (sklearn 0.23.2 format). "
                                "Using XGBoost model directly to bypass version incompatibility."
                            )
                            # Extract the XGBoost model and feature order
                            # Since preprocessing is just passthrough, we can use XGB directly
                            xgb_model = model.named_steps["model"]

                            # Get feature order from numeric transformer (which has all features)
                            feature_order = None
                            for name, _transformer, features in transformers_list:
                                if name == "num" and isinstance(features, list):
                                    feature_order = features
                                    break

                            # Store feature order for use during prediction
                            if feature_order:
                                model._aeris_exposure_feature_order = feature_order
                                model._aeris_exposure_use_direct_xgb = True
                                model._aeris_exposure_xgb_model = xgb_model

                self._model = model
        return self._model

    def _get_openaq_pm25(
        self, lat: float, lon: float, dt_iso_start: str, dt_iso_end: str
    ) -> Optional[float]:
        """
        Query OpenAQ for PM2.5 measurement at a specific location and time window.

        This is used as a fallback when no PurpleAir sensors are available within 5km.
        Searches within 25km radius to find OpenAQ stations.
        Uses the same pattern as the static OpenAQ estimator.

        Args:
            lat: Latitude
            lon: Longitude
            dt_iso_start: Start datetime in ISO format
            dt_iso_end: End datetime in ISO format

        Returns:
            PM2.5 value in µg/m³, or None if no data available
        """
        if self.openaq is None:
            return None

        try:
            # Search for stations within 25km (25000m) of the target coordinates
            radius_25km = 25000
            logger.debug("Querying OpenAQ for PM2.5 within 25km of (%.4f, %.4f)", lat, lon)

            stations = self.openaq.list_locations(
                coordinates=(lat, lon), radius=radius_25km, limit=self.config.station_limit
            ).results

            if not stations:
                logger.debug("No OpenAQ stations within 25km of (%.4f, %.4f)", lat, lon)
                return None

            # Sort stations by distance and find the nearest with PM2.5 data
            # This minimizes API calls by querying nearest stations first
            from ..utils import haversine

            # Build list of (distance, location, sensor) tuples for stations with PM2.5 sensors
            station_sensors = []
            for loc in stations:
                coords = loc.coordinates
                st_lat = coords.get("latitude") if isinstance(coords, dict) else coords.latitude
                st_lon = coords.get("longitude") if isinstance(coords, dict) else coords.longitude
                distance = haversine(lat, lon, st_lat, st_lon)

                # Check if this location has a PM2.5 sensor
                for sensor in loc.sensors or []:
                    param_name = (
                        getattr(sensor.parameter, "name", "")
                        if hasattr(sensor.parameter, "name")
                        else (
                            sensor.parameter.get("name")
                            if isinstance(sensor.parameter, dict)
                            else ""
                        )
                    )

                    if param_name.lower() == "pm25":
                        station_sensors.append((distance, loc, sensor))

            # Sort by distance (nearest first) to minimize API calls
            station_sensors.sort(key=lambda x: x[0])

            # Query measurements starting from the nearest station
            for distance, _loc, sensor in station_sensors:
                try:
                    resp = self.openaq.list_measurements(
                        sensors_id=sensor.id,
                        data="hours",
                        datetime_from=dt_iso_start,
                        datetime_to=dt_iso_end,
                        limit=10,  # Only need a few measurements for the hour
                        page=1,
                    )

                    if resp.results:
                        # Extract PM2.5 value from measurements
                        # Handle both dict and object formats (similar to static estimator)
                        for measurement in resp.results:
                            # Try to get value - handle both object and dict formats
                            value = None
                            if hasattr(measurement, "value"):
                                value = measurement.value
                            elif isinstance(measurement, dict):
                                value = measurement.get("value")

                            if value is not None:
                                try:
                                    pm25_val = float(value)
                                    logger.debug(
                                        "Found OpenAQ PM2.5: %.2f µg/m³ at %.1fm from (%.4f, %.4f)",
                                        pm25_val,
                                        distance,
                                        lat,
                                        lon,
                                    )
                                    return pm25_val  # Return immediately when found (nearest station with data)
                                except (ValueError, TypeError):
                                    continue
                except (requests.RequestException, KeyError, ValueError) as e:
                    logger.debug(
                        "Failed to fetch OpenAQ measurements for sensor %s: %s", sensor.id, e
                    )
                    continue  # Try next nearest station

            # No PM2.5 data found from any station
            logger.debug(
                "No OpenAQ PM2.5 data available for (%.4f, %.4f) at %s", lat, lon, dt_iso_start
            )
            return None

        except (requests.RequestException, RuntimeError) as e:
            logger.warning(
                "OpenAQ query failed for (%.4f, %.4f) at %s: %s", lat, lon, dt_iso_start, e
            )
            return None

    def _feature_row(
        self, lat: float, lon: float, dt_iso_start: str, dt_iso_end: str, dt_floor: pd.Timestamp
    ) -> dict[str, Any]:
        # PurpleAir nearest reading proxy; if unavailable within 5km, try OpenAQ fallback
        # Use a 5 km radius to match the OpenAQ fallback threshold
        pa_near = self.pa.nearest_sensor(lat, lon, radius_m=5000)
        re_pm25 = None
        pa_source = None

        if pa_near:
            fields = pa_near["fields"]
            row = pa_near["row"]
            idx_pm60 = fields.index("pm2.5_60minute") if "pm2.5_60minute" in fields else None
            idx_pm = fields.index("pm2.5") if "pm2.5" in fields else None
            if idx_pm60 is not None and row[idx_pm60] is not None:
                re_pm25 = float(row[idx_pm60])
                pa_source = "PurpleAir"
            elif idx_pm is not None and row[idx_pm] is not None:
                re_pm25 = float(row[idx_pm])
                pa_source = "PurpleAir"

        # If no PurpleAir sensor within 5km, fall back to OpenAQ if available
        if re_pm25 is None and self.openaq is not None:
            logger.info(
                "No PurpleAir sensor within 5km, attempting OpenAQ fallback for (%.4f, %.4f)",
                lat,
                lon,
            )
            openaq_pm25 = self._get_openaq_pm25(lat, lon, dt_iso_start, dt_iso_end)
            if openaq_pm25 is not None:
                re_pm25 = openaq_pm25
                pa_source = "OpenAQ"
                logger.info("Using OpenAQ PM2.5 fallback: %.2f µg/m³", re_pm25)
            else:
                logger.info("No OpenAQ PM2.5 data available within 25km for (%.4f, %.4f)", lat, lon)

        # Meteorology
        met = self.met.get_hourly(lat, lon, dt_iso_start, dt_iso_end)
        m_hour = {
            "temperature": None,
            "humidity": None,
            "windspeed": None,
            "winddirection": None,
            "precipitation": None,
        }
        try:
            hourly = met.get("hourly", {})
            m_hour["temperature"] = float(hourly.get("temperature_2m", [None])[0])
            m_hour["humidity"] = float(hourly.get("relative_humidity_2m", [None])[0])
            m_hour["windspeed"] = float(hourly.get("windspeed_10m", [None])[0])
            m_hour["winddirection"] = float(hourly.get("winddirection_10m", [None])[0])
            m_hour["precipitation"] = float(hourly.get("precipitation", [None])[0])
        except (TypeError, ValueError, KeyError, IndexError):
            pass

        # Roads distance
        logger.debug("Querying Overpass for road distances at (%.4f, %.4f)", lat, lon)
        roads = self.osm.dist_to_roads(lat, lon)
        logger.debug(
            "Road distances: dist_hwy=%.1f m, dist_art=%.1f m",
            roads.get("dist_hwy") or 0,
            roads.get("dist_art") or 0,
        )

        # Land variables: Google Earth Engine is the PRIMARY source (per collaborator requirements)
        land = {"OS": None, "WA": None, "ISF": None, "TC": None, "EL": None}
        if self.gee is not None:
            try:
                logger.debug(
                    "Fetching LULC variables from Google Earth Engine at (%.4f, %.4f)", lat, lon
                )
                land = self.gee.get_variables(lat, lon)
                success_count = sum(1 for v in land.values() if v is not None)
                logger.debug(
                    "GEE retrieved %d/%d LULC variables at (%.4f, %.4f)",
                    success_count,
                    len(land),
                    lat,
                    lon,
                )
            except (RuntimeError, ValueError) as e:
                logger.error("GEE fetch failed at (%.4f, %.4f): %s", lat, lon, e, exc_info=True)
                land = {"OS": None, "WA": None, "ISF": None, "TC": None, "EL": None}
        else:
            logger.error("GEE not available - LULC variables will be None")

        weekday = 1 if dt_floor.weekday() < 5 else 0

        # Feature order MUST match training order from notebook:
        # "re_pm25", "temperature","humidity","windspeed","winddirection","precipitation",
        # "dist_hwy","dist_art","OS","WA","ISF","TC","EL","weekday"
        feats = {
            "re_pm25": re_pm25,
            "temperature": m_hour["temperature"],
            "humidity": m_hour["humidity"],
            "windspeed": m_hour["windspeed"],
            "winddirection": m_hour["winddirection"],
            "precipitation": m_hour["precipitation"],
            "dist_hwy": roads.get("dist_hwy"),
            "dist_art": roads.get("dist_art"),
            "OS": land.get("OS"),
            "WA": land.get("WA"),
            "ISF": land.get("ISF"),
            "TC": land.get("TC"),
            "EL": land.get("EL"),
            "weekday": weekday,
        }
        logger.debug(
            "Feature row LULC values: WA=%s, OS=%s, ISF=%s, TC=%s, EL=%s",
            feats.get("WA"),
            feats.get("OS"),
            feats.get("ISF"),
            feats.get("TC"),
            feats.get("EL"),
        )

        # Warn if critical features are missing
        missing_critical = []
        if feats.get("re_pm25") is None:
            if self.openaq is not None:
                missing_critical.append("re_pm25 (PurpleAir/OpenAQ)")
            else:
                missing_critical.append("re_pm25 (PurpleAir)")
        if feats.get("temperature") is None:
            missing_critical.append("temperature")
        if feats.get("humidity") is None:
            missing_critical.append("humidity")
        if feats.get("dist_hwy") is None and feats.get("dist_art") is None:
            missing_critical.append("road_distances (Overpass)")
        if all(
            v is None
            for v in [
                feats.get("WA"),
                feats.get("OS"),
                feats.get("ISF"),
                feats.get("TC"),
                feats.get("EL"),
            ]
        ):
            missing_critical.append("all_LULC_variables (GEE)")

        if missing_critical:
            logger.warning(
                "Missing critical features at (%.4f, %.4f): %s. Model predictions may be inaccurate.",
                lat,
                lon,
                ", ".join(missing_critical),
            )
        elif pa_source and re_pm25 is not None:
            logger.info(
                "PM2.5 source for (%.4f, %.4f): %s (%.2f µg/m³)", lat, lon, pa_source, re_pm25
            )

        return feats

    def run(
        self,
        output_csv: Optional[str] = None,
        raw_output: bool = False,
        skip_confirm: bool = False,
    ) -> pd.DataFrame:
        try:
            self.read_and_validate_input()
            df = self.df_input
            assert df is not None

            model = self._load_model()

            raw_dir = Path.cwd() / "raw_gps_xgb"
            if raw_output:
                raw_dir.mkdir(parents=True, exist_ok=True)

            all_summary_rows: list[dict] = []
            all_route_rows: list[dict] = []
            all_tidy_pm25: list[pd.DataFrame] = []
            all_predictions: list[Optional[float]] = []

            subjects = df.groupby("subject_id", sort=False)
            for sid, subj_df in tqdm(subjects, desc="Subjects", unit="subj"):
                rows: list[dict[str, Any]] = []
                tidy_pm25: list[pd.DataFrame] = []
                predictions: list[Optional[float]] = []

                for r in tqdm(
                    subj_df.itertuples(),
                    total=len(subj_df),
                    desc=f"  GPS [{sid}]",
                    unit="pt",
                    leave=False,
                ):
                    lat, lon, dt = float(r.latitude), float(r.longitude), r.dt
                    dt_floor = pd.Timestamp(dt).floor("h")
                    start_iso = dt_floor.strftime("%Y-%m-%dT%H:%M:%SZ")
                    end_iso = (dt_floor + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

                    feats = self._feature_row(lat, lon, start_iso, end_iso, dt_floor)
                    import numpy as np

                    X = pd.DataFrame([feats])
                    X = X.replace(
                        {None: np.nan, "None": np.nan, "nan": np.nan, "NaN": np.nan}
                    ).infer_objects(copy=False)
                    for col in X.columns:
                        if col == "weekday":
                            try:
                                X[col] = (
                                    pd.to_numeric(X[col], errors="coerce").fillna(0).astype(int)
                                )
                            except (AttributeError, IndexError):
                                X[col] = 0
                        else:
                            X[col] = pd.to_numeric(X[col], errors="coerce")
                    try:
                        feats_expected = getattr(model, "feature_names_in_", None)
                        if feats_expected is not None:
                            missing = [c for c in feats_expected if c not in X.columns]
                            if missing:
                                logger.warning(
                                    "Model expects features not in DataFrame: %s. Setting to NaN.",
                                    missing,
                                )
                            for mcol in missing:
                                X[mcol] = np.nan
                            X = X.reindex(columns=list(feats_expected))
                    except (AttributeError, KeyError):
                        pass
                    try:
                        import xgboost as xgb

                        if isinstance(model, xgb.Booster):
                            feat_order = None
                            if self.config.xgb_feature_names_path:
                                try:
                                    with open(self.config.xgb_feature_names_path) as f:
                                        feat_order = [ln.strip() for ln in f if ln.strip()]
                                except (OSError, ValueError) as _e:
                                    logger.warning(
                                        "Failed reading feature list %s (%s). Using DataFrame order.",
                                        self.config.xgb_feature_names_path,
                                        _e,
                                    )
                            Xb = X
                            if feat_order:
                                missing = [c for c in feat_order if c not in Xb.columns]
                                if missing:
                                    logger.warning(
                                        "Feature order file expects features not in DataFrame: %s. Setting to NaN.",
                                        missing,
                                    )
                                for mcol in missing:
                                    Xb[mcol] = np.nan
                                Xb = Xb.reindex(columns=feat_order)
                            else:
                                logger.warning(
                                    "No feature order file provided for Booster model. Using DataFrame column order, which may not match training order!"
                                )
                            dmat = xgb.DMatrix(Xb)
                            yhat = float(model.predict(dmat)[0])
                        elif getattr(model, "_aeris_exposure_use_direct_xgb", False):
                            feat_order = model._aeris_exposure_feature_order
                            xgb_model = model._aeris_exposure_xgb_model
                            if feat_order:
                                missing = [c for c in feat_order if c not in X.columns]
                                for mcol in missing:
                                    X[mcol] = np.nan
                                X = X.reindex(columns=feat_order)
                            yhat = float(xgb_model.predict(X)[0])
                        else:
                            yhat = float(model.predict(X)[0])
                    except (ValueError, TypeError, RuntimeError) as e:
                        logger.warning(
                            "Model prediction failed at (%.4f, %.4f, %s): %s",
                            lat,
                            lon,
                            start_iso,
                            e,
                        )
                        yhat = None

                    predictions.append(yhat)

                    ts_utc = (
                        dt_floor.tz_convert("UTC")
                        if getattr(dt_floor, "tzinfo", None)
                        else dt_floor.tz_localize("UTC")
                    )
                    out = {
                        "timestamp_utc": ts_utc,
                        "latitude": lat,
                        "longitude": lon,
                        "pm25": yhat,
                    }
                    rows.append(out)

                    if yhat is not None:
                        tidy_pm25.append(
                            pd.DataFrame(
                                {
                                    "timestamp_utc": [dt_floor],
                                    "value": [yhat],
                                    "parameter": ["pm25"],
                                    "unit": ["µg/m³"],
                                    "latitude": [lat],
                                    "longitude": [lon],
                                }
                            )
                        )

                # Raw output for this subject
                if raw_output:
                    original_df = pd.read_csv(self.input_csv, dtype=str)
                    subj_orig = original_df[
                        original_df["subject_id"].astype(str) == str(sid)
                    ].copy()

                    prediction_map = {}
                    for idx, (_, processed_row) in enumerate(subj_df.iterrows()):
                        hour_key = pd.Timestamp(processed_row["dt"]).floor("h")
                        plat = float(processed_row["latitude"])
                        plon = float(processed_row["longitude"])
                        prediction_map[(hour_key, plat, plon)] = predictions[idx]

                    predicted_values = []
                    for _, orig_row in subj_orig.iterrows():
                        try:
                            orig_dt = pd.to_datetime(
                                orig_row["timestamp"], utc=True, errors="coerce"
                            )
                            orig_hour = orig_dt.floor("h") if pd.notna(orig_dt) else None
                            orig_lat = pd.to_numeric(orig_row["latitude"], errors="coerce")
                            orig_lon = pd.to_numeric(orig_row["longitude"], errors="coerce")
                            if pd.notna(orig_hour) and pd.notna(orig_lat) and pd.notna(orig_lon):
                                pred_value = prediction_map.get(
                                    (orig_hour, float(orig_lat), float(orig_lon))
                                )
                                predicted_values.append(pred_value)
                            else:
                                predicted_values.append(None)
                        except (ValueError, TypeError, KeyError):
                            predicted_values.append(None)

                    subj_orig["predicted_pm25"] = predicted_values
                    subj_orig["predicted_pm25"] = pd.to_numeric(
                        subj_orig["predicted_pm25"], errors="coerce"
                    ).round(3)
                    raw_output_path = raw_dir / f"{sid}_predictions.csv"
                    subj_orig.to_csv(raw_output_path, index=False)
                    logger.info("Raw output written → %s", raw_output_path)

                # Summary for this subject
                units_map = {"pm25": "µg/m³"}
                expected_hours = len(subj_df)
                if tidy_pm25:
                    df_pm = pd.concat(tidy_pm25, ignore_index=True)
                    m = calculate_metrics(
                        df_pm[["timestamp_utc", "value", "parameter", "unit"]],
                        "pm25",
                        threshold=getattr(self, "threshold", None),
                        expected_hours=expected_hours,
                    )

                    aqi_val, aqi_cat = None, None
                    if m["mean"] is not None:
                        with contextlib.suppress(ValueError):
                            aqi_val, aqi_cat = concentration_to_aqi(m["mean"], "pm25")

                    row_dict = {
                        "subject_id": sid,
                        "pollutant": "pm25",
                        "mean": m["mean"],
                        "std": m["std"],
                        "median": m["median"],
                        "min": m["min"],
                        "max": m["max"],
                        "n_samples": m["n_samples"],
                        "aqi": aqi_val,
                        "aqi_category": aqi_cat,
                        "unit": units_map["pm25"],
                    }
                    if "exceedance_count" in m:
                        row_dict["exceedance_count"] = m["exceedance_count"]
                        row_dict["exceedance_pct"] = m["exceedance_pct"]
                        row_dict["exceedance_threshold"] = m["exceedance_threshold"]
                    if "completeness_pct" in m:
                        row_dict["completeness_pct"] = m["completeness_pct"]
                        if self.min_completeness is not None:
                            row_dict["qc_flag"] = (
                                "PASS" if m["completeness_pct"] >= self.min_completeness else "FAIL"
                            )
                    all_summary_rows.append(row_dict)

                all_route_rows.extend(rows)
                all_tidy_pm25.extend(tidy_pm25)
                all_predictions.extend(predictions)

            df_out = pd.DataFrame(all_summary_rows) if all_summary_rows else pd.DataFrame()

            # Output
            pd.set_option("display.max_columns", None, "display.width", None)
            print("\nExposure-metric summary (XGB Dispersion · DYNAMIC · PM2.5):\n")
            if df_out.empty:
                logger.warning("No summary metrics (no predictions).")
            else:
                print(df_out.to_string(index=False, float_format="%.3f"), "\n")

            if output_csv and not df_out.empty:
                df_out.to_csv(output_csv, index=False)
                logger.info("Summary written → %s", output_csv)

            # Plots
            df_route = pd.DataFrame(all_route_rows)
            if not df_route.empty:
                self.plotter.plot_route_map(
                    df_route.rename(columns={"pm25": "pm25"}),
                    "pm25",
                    units_map["pm25"],
                )
                self.plotter.plot_boxplots(df_route, units_map)

            n_subjects = df["subject_id"].nunique()
            logger.info("All done - %d subject(s) processed with XGBoost dispersion.", n_subjects)
            return df_out
        except Exception as e:  # Boundary catch-all: top-level run() must not propagate
            logger.error("Fatal error - %s", e)
            return pd.DataFrame()

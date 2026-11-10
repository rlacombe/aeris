"""
Command-line interface for the exposure estimator package.
"""

import argparse
import logging
import sys
import warnings
from pathlib import Path
from typing import Optional

from .config import ALLOWED_POLLUTANTS
from .estimators import (
    ExposureEstimatorGoogleMapsDynamic,
    ExposureEstimatorOpenAQStatic,
    ExposureEstimatorXGBDynamic,
)
from .exceptions import ConfigurationError, ExposureEstimatorError
from .validators import detect_mode

# Suppress Google API version warnings (Python 3.10 deprecation)
warnings.filterwarnings("ignore", category=FutureWarning, module="google.api_core")


def setup_logging(debug: bool = False) -> None:
    """Configure logging for the CLI."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        stream=sys.stdout,
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Silence noisy dependencies
    for noisy in ("matplotlib", "httpx", "httpcore", "openaq", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Estimate air-pollution exposure in two modes.\n"
            "Static: OpenAQ for ZIP/Address + date range (choose ONE pollutant).\n"
            "Dynamic: Google Maps AQ (all) or XGB dispersion model (PM2.5)."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Static mode with OpenAQ\n"
            "  aeris exposure data.csv --pollutant pm25 --output_csv results.csv\n"
            "  \n"
            "  # Dynamic mode with Google Maps Air Quality\n"
            "  aeris exposure gps_data.csv --dynamic_backend gmaps --output_csv results.csv\n"
            "  \n"
            "  # Dynamic mode with XGB dispersion model (PM2.5)\n"
            "  aeris exposure gps_data.csv --dynamic_backend xgb --model_path model.joblib --output_csv results.csv\n"
            "  \n"
            "  # With custom API keys\n"
            "  aeris exposure data.csv --pollutant pm25 --api_key YOUR_OPENAQ_KEY\n"
            "  aeris exposure gps_data.csv --dynamic_backend gmaps --gmaps_api_key YOUR_GMAPS_KEY\n"
            "  aeris exposure gps_data.csv --dynamic_backend xgb --purpleair_api_key YOUR_PA_KEY --model_path MODEL.joblib\n"
            "  # XGB mode with OpenAQ fallback (when no PurpleAir within 5km):\n"
            "  aeris exposure gps_data.csv --dynamic_backend xgb --purpleair_api_key YOUR_PA_KEY --api_key YOUR_OPENAQ_KEY --model_path MODEL.joblib\n"
            "\n"
            "Environment Variables:\n"
            "  OPENAQ_API_KEY - OpenAQ API key for static mode or XGB dynamic fallback\n"
            "  GOOGLE_MAPS_AIR_QUALITY_API_KEY - Google Maps Air Quality API key for dynamic mode\n"
            "  PURPLEAIR_API_KEY - PurpleAir API key (required for XGB dynamic)\n"
            "  AERIS_EXPOSURE_XGB_MODEL_PATH - Default path to XGB model file\n"
            "\n"
            "Note: In XGB dynamic mode, if OPENAQ_API_KEY is provided, the system will\n"
            "automatically query OpenAQ for PM2.5 (within 25km) when no PurpleAir sensors\n"
            "are found within 5km."
        ),
    )

    # Input file
    parser.add_argument("input_csv", help="Path to input CSV file")

    # Output options
    parser.add_argument("--output_csv", help="Path for output summary CSV file")
    parser.add_argument("--raw", action="store_true", help="Save raw measurement data as CSV files")

    # Static mode options
    parser.add_argument(
        "--pollutant",
        choices=[*ALLOWED_POLLUTANTS, "all"],
        help="[STATIC + OpenAQ ONLY] Pollutant to analyze (pm25, pm10, so2, no2, co, o3, all)",
    )
    parser.add_argument(
        "--distance_threshold",
        type=float,
        help="[STATIC ONLY] Auto-exclude participants beyond this distance (km)",
    )
    parser.add_argument(
        "--country",
        type=str,
        default="us",
        help="ISO 3166-1 alpha-2 country code for ZIP/postal geocoding (default: us)",
    )
    # No static_source: static mode uses OpenAQ only

    # API keys
    parser.add_argument(
        "--api_key",
        help="OpenAQ API key (or set OPENAQ_API_KEY env var). Used for static mode or XGB dynamic mode fallback.",
    )
    parser.add_argument(
        "--gmaps_api_key",
        help="Google Maps Air Quality API key (or set GOOGLE_MAPS_AIR_QUALITY_API_KEY)",
    )
    parser.add_argument(
        "--purpleair_api_key",
        help="PurpleAir API key (or set PURPLEAIR_API_KEY)",
    )
    parser.add_argument(
        "--dynamic_backend",
        choices=["gmaps", "xgb"],
        default="gmaps",
        help="[DYNAMIC ONLY] Backend: 'gmaps' (all pollutants) or 'xgb' (PM2.5)",
    )
    parser.add_argument(
        "--model_path",
        help="[DYNAMIC xgb] Path to joblib model file (defaults to env or project root)",
    )

    # Daily aggregation output
    parser.add_argument(
        "--daily",
        metavar="DAILY_CSV",
        help="Path for daily-aggregated output CSV (static mode only)",
    )

    # Threshold for exceedance counts
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Concentration threshold for exceedance counting",
    )

    # Data completeness QC
    parser.add_argument(
        "--min_completeness",
        type=float,
        default=None,
        help="Minimum data completeness %% (0-100). Subjects below this threshold are flagged.",
    )

    # IDW multi-station averaging
    parser.add_argument(
        "--n_stations",
        type=int,
        default=1,
        help="[STATIC ONLY] Number of stations for IDW averaging (default: 1 = nearest only)",
    )
    parser.add_argument(
        "--temporal_resolution",
        choices=["hourly", "daily"],
        default="hourly",
        help="[STATIC ONLY] OpenAQ retrieval resolution. Use daily for daily epidemiologic analyses.",
    )
    parser.add_argument(
        "--location_strategy",
        choices=["auto", "per_subject", "catalog"],
        default="auto",
        help="[STATIC ONLY] OpenAQ station discovery strategy (default: auto).",
    )

    # Outlier detection
    parser.add_argument(
        "--outlier_detection",
        action="store_true",
        help="Enable IQR-based outlier detection and negative-value removal",
    )

    # Output format
    parser.add_argument(
        "--format",
        choices=["csv", "geojson"],
        default="csv",
        dest="output_format",
        help="Output format: csv (default) or geojson (dynamic mode only, requires geopandas)",
    )

    # Long-format tidy output
    parser.add_argument(
        "--long_format",
        metavar="LONG_CSV",
        help="Path for long-format (tidy) output CSV (one row per subject-pollutant-time)",
    )

    # Caching
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Enable SQLite response caching for resume-on-failure",
    )
    parser.add_argument(
        "--cache_path",
        type=str,
        default=None,
        help="Path to cache DB file (default: .aeris_exposure_cache.db in current directory)",
    )
    parser.add_argument(
        "--clear_cache",
        action="store_true",
        help="Clear the response cache and exit",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default=None,
        help="Directory for outputs and plots. Created if missing.",
    )

    # Other options
    parser.add_argument(
        "--yes", "-y", action="store_true", help="Skip interactive confirmation prompt"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.debug)
    logger = logging.getLogger("ExposureEstimator")

    def resolve_output_path(path: Optional[str]) -> Optional[str]:
        if path is None or args.output_dir is None or Path(path).is_absolute():
            return path
        return str(Path(args.output_dir) / path)

    # Handle --clear_cache
    if args.clear_cache:
        from .cache import ResponseCache

        cache = ResponseCache(db_path=args.cache_path)
        cache.clear()
        cache.close()
        print("Cache cleared.")
        return

    # Build cache instance if requested
    cache = None
    if args.cache:
        from .cache import ResponseCache

        cache = ResponseCache(db_path=args.cache_path)

    output_dir = Path(args.output_dir) if args.output_dir else None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Writing outputs under %s", output_dir.resolve())

    try:
        # Validate input file exists
        input_path = Path(args.input_csv)
        if not input_path.exists():
            logger.error("Input file not found: %s", args.input_csv)
            sys.exit(1)

        # Detect mode and create appropriate estimator
        mode = detect_mode(args.input_csv)
        logger.info("Detected mode: %s", mode.upper())

        if mode == "static":
            if not args.pollutant:
                logger.error("STATIC mode requires --pollutant argument (or --pollutant all)")
                sys.exit(1)
            static_options = {}
            if args.temporal_resolution != "hourly":
                static_options["temporal_resolution"] = args.temporal_resolution
            if args.location_strategy != "auto":
                static_options["location_strategy"] = args.location_strategy
            if output_dir is not None:
                static_options["output_dir"] = output_dir
            estimator = ExposureEstimatorOpenAQStatic(
                input_csv=args.input_csv,
                pollutant=args.pollutant,
                api_key=args.api_key,
                distance_threshold_km=args.distance_threshold,
                country=args.country,
                min_completeness=args.min_completeness,
                    cache=cache,
                    n_stations=args.n_stations,
                    outlier_detection=args.outlier_detection,
                    **static_options,
            )

        else:  # dynamic
            if args.dynamic_backend == "gmaps":
                if args.pollutant:
                    logger.info(
                        "Note: --pollutant is ignored in DYNAMIC mode (Google AQ processes all six pollutants)."
                    )
                estimator = ExposureEstimatorGoogleMapsDynamic(
                    input_csv=args.input_csv,
                    gmaps_api_key=args.gmaps_api_key,
                    cache=cache,
                    **({"output_dir": str(output_dir)} if output_dir else {}),
                )
            else:
                estimator = ExposureEstimatorXGBDynamic(
                    input_csv=args.input_csv,
                    purpleair_api_key=args.purpleair_api_key,
                    openaq_api_key=args.api_key,  # Use OpenAQ API key for fallback in XGB mode
                    model_path=args.model_path,
                    cache=cache,
                    **({"output_dir": str(output_dir)} if output_dir else {}),
                )

        # Set threshold for exceedance counting
        if args.threshold is not None:
            estimator.threshold = args.threshold

        # Run the analysis
        result_df = estimator.run(
            output_csv=resolve_output_path(args.output_csv), raw_output=args.raw, skip_confirm=args.yes
        )

        if result_df.empty:
            logger.warning("No results generated. Check your input data and API keys.")
            sys.exit(1)
        else:
            logger.info("Analysis completed successfully!")

        # GeoJSON output (dynamic mode only)
        if args.output_format == "geojson" and args.output_csv:
            if mode == "dynamic":
                try:
                    import geopandas as gpd
                    from shapely.geometry import Point

                    if "latitude" in result_df.columns and "longitude" in result_df.columns:
                        geometry = [
                            Point(xy) for xy in zip(result_df["longitude"], result_df["latitude"])
                        ]
                        gdf = gpd.GeoDataFrame(result_df, geometry=geometry, crs="EPSG:4326")
                        geojson_path = resolve_output_path(args.output_csv).replace(".csv", ".geojson")
                        gdf.to_file(geojson_path, driver="GeoJSON")
                        logger.info("GeoJSON written → %s", geojson_path)
                    else:
                        logger.warning("GeoJSON requires latitude/longitude columns in output.")
                except ImportError:
                    logger.warning(
                        "GeoJSON output requires geopandas. "
                        "Install with: pip install 'aeris[geo]'"
                    )
            else:
                logger.warning("--format geojson is only supported in dynamic mode.")

        # Long-format tidy output
        if args.long_format:
            if mode == "static" and hasattr(estimator, "get_raw_data"):
                raw_df = estimator.get_raw_data()
                if not raw_df.empty:
                    long_format_path = resolve_output_path(args.long_format)
                    raw_df.to_csv(long_format_path, index=False)
                    logger.info("Long-format data written → %s", long_format_path)
                else:
                    logger.warning("No raw data available for long-format output.")
            elif mode == "dynamic":
                logger.warning("--long_format for dynamic mode: use --raw instead.")
            else:
                logger.warning("Long-format output not available.")

        # Daily aggregation output (static mode only)
        if args.daily:
            if mode == "static":
                daily_df = estimator.get_daily_data()
                if not daily_df.empty:
                    daily_path = resolve_output_path(args.daily)
                    daily_df.to_csv(daily_path, index=False)
                    logger.info("Daily data written → %s", daily_path)
                else:
                    logger.warning("No daily data to write.")
            else:
                logger.warning("--daily is only supported in static mode; ignoring.")

    except ConfigurationError as e:
        logger.error("Configuration error: %s", e)
        sys.exit(1)
    except ExposureEstimatorError as e:
        logger.error("Analysis error: %s", e)
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Analysis interrupted by user.")
        sys.exit(0)
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=args.debug)
        sys.exit(1)


def main_cli() -> None:
    """CLI entry point for package installation."""
    main()


if __name__ == "__main__":
    main_cli()

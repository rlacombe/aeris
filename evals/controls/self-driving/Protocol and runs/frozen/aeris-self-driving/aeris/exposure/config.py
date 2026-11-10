"""
Configuration management for the exposure estimator package.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Optional .env file support
try:
    from dotenv import load_dotenv

    HAS_DOTENV = True
except ImportError:
    HAS_DOTENV = False

# Package constants
ALLOWED_POLLUTANTS = ["pm25", "pm10", "so2", "no2", "co", "o3"]

# Matplotlib styling constants
TITLE_SIZE = 16
LABEL_SIZE = 14
TICK_SIZE = 12
BASE_FONTSZ = 12
LEGEND_SIZE = 12
CB_LABEL_SZ = 12
CB_TICK_SZ = 12


@dataclass
class Config:
    """Configuration container for the exposure estimator."""

    # API Keys
    openaq_api_key: Optional[str] = None
    google_maps_api_key: Optional[str] = None
    purpleair_api_key: Optional[str] = None
    accuweather_api_key: Optional[str] = None
    # Optional: path to XGBoost PM2.5 dispersion model (joblib)
    xgb_model_path: Optional[str] = None
    # Optional: feature names file (one per line) for Booster JSON
    xgb_feature_names_path: Optional[str] = None

    # Rate limiting
    openaq_calls_per_minute: int = 50
    openaq_calls_per_hour: int = 2000

    # OpenAQ settings
    search_radius: int = 25000  # 25km in meters
    station_limit: int = 1000
    # Annual study windows can be recovered automatically from the public S3
    # archive. Longer windows are planned first, which prevents a national
    # panel from silently starting a large archive download.
    archive_fallback_max_days: int = 400
    archive_fallback_max_objects: int = 500
    archive_fallback_enabled: bool = True

    # Plotting
    generate_plots: bool = True
    dpi: int = 300

    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "Config":
        """
        Create configuration from environment variables.

        Args:
            env_file: Optional path to .env file to load

        Returns:
            Config instance with values from environment variables
        """
        # Load .env file if requested and available
        configured_env_file = env_file or os.getenv("AERIS_ENV_FILE")
        if configured_env_file and HAS_DOTENV:
            load_dotenv(configured_env_file, override=False)
        elif HAS_DOTENV:
            # Prefer an explicit study workspace, then the repository root
            # when running AERIS from source. Existing process variables win.
            candidates = (Path.cwd() / ".env", get_package_root().parent / ".env")
            for env_path in candidates:
                if env_path.exists():
                    load_dotenv(env_path, override=False)
                    break

        return cls(
            openaq_api_key=os.getenv("OPENAQ_API_KEY"),
            google_maps_api_key=os.getenv("GOOGLE_MAPS_AIR_QUALITY_API_KEY"),
            purpleair_api_key=os.getenv("PURPLEAIR_API_KEY"),
            accuweather_api_key=os.getenv("ACCUWEATHER_API_KEY"),
            xgb_model_path=os.getenv("AERIS_EXPOSURE_XGB_MODEL_PATH"),
            xgb_feature_names_path=os.getenv("AERIS_EXPOSURE_XGB_FEATURES"),
            archive_fallback_max_days=int(os.getenv("AERIS_ARCHIVE_FALLBACK_MAX_DAYS", "400")),
            archive_fallback_max_objects=int(
                os.getenv("AERIS_ARCHIVE_FALLBACK_MAX_OBJECTS", "500")
            ),
            archive_fallback_enabled=os.getenv("AERIS_ARCHIVE_FALLBACK_ENABLED", "true").lower()
            not in {"0", "false", "no"},
        )


def get_package_root() -> Path:
    """Get the root directory of the package."""
    return Path(__file__).parent.parent

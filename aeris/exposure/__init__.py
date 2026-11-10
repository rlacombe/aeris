"""
AERIS Exposure: A Python package for estimating personal air pollution exposure.

This package democratizes access to air quality data for public health investigators,
epidemiologists, and the broader research community. It transforms subjects' location data
into analysis-ready metrics of air pollution exposure, supporting both monitoring networks
and dispersion models.

The package provides multiple modes for estimating air pollution exposure:
1. Static mode: Uses monitoring networks (e.g., OpenAQ) for subjects with ZIP codes/addresses and date ranges
2. Dynamic mode: Uses dispersion models (e.g., Google Maps Air Quality API, XGBoost) for GPS-tracked subjects

Main classes:
- ExposureEstimatorOpenAQStatic: For static exposure estimation with OpenAQ
- ExposureEstimatorGoogleMapsDynamic: For dynamic exposure estimation with Google Maps
- ExposureEstimatorXGBDynamic: For dynamic exposure estimation with XGBoost dispersion model
  (includes automatic OpenAQ fallback when no PurpleAir sensors are within 5km)
- detect_mode: Utility function to detect input mode from CSV structure
"""

from .config import ALLOWED_POLLUTANTS, Config
from .estimators import (
    ExposureEstimatorGoogleMapsDynamic,
    ExposureEstimatorOpenAQBoundary,
    ExposureEstimatorOpenAQStatic,
    ExposureEstimatorXGBDynamic,
)
from .exceptions import (
    APIRateLimitError,
    ConfigurationError,
    ExposureEstimatorError,
    GeocodingError,
    InputValidationError,
    UpstreamAPIError,
)
from .utils import (
    calculate_metrics,
    concentration_to_aqi,
    flag_outliers,
    idw_average,
    idw_hourly_series,
    time_weighted_mean,
)
from .validators import detect_mode

__version__ = "0.1.0"

__all__ = [
    "ALLOWED_POLLUTANTS",
    "APIRateLimitError",
    "Config",
    "ConfigurationError",
    "ExposureEstimatorError",
    "ExposureEstimatorGoogleMapsDynamic",
    "ExposureEstimatorOpenAQBoundary",
    "ExposureEstimatorOpenAQStatic",
    "ExposureEstimatorXGBDynamic",
    "GeocodingError",
    "InputValidationError",
    "UpstreamAPIError",
    "calculate_metrics",
    "concentration_to_aqi",
    "detect_mode",
    "flag_outliers",
    "idw_average",
    "idw_hourly_series",
    "time_weighted_mean",
]

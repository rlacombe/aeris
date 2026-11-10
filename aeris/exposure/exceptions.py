"""
Custom exceptions for the exposure estimator package.
"""


class ExposureEstimatorError(Exception):
    """Base class for all estimator-specific errors."""

    pass


class ConfigurationError(ExposureEstimatorError):
    """Configuration issues like missing API keys, invalid parameters, etc."""

    pass


class InputValidationError(ExposureEstimatorError):
    """Input data validation errors."""

    pass


class GeocodingError(ExposureEstimatorError):
    """Geocoding service failures."""

    pass


class APIRateLimitError(ExposureEstimatorError):
    """API rate limit exceeded."""

    pass


class UpstreamAPIError(ExposureEstimatorError):
    """Third-party API errors."""

    pass

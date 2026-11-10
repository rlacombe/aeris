"""
Tests for the custom exception hierarchy.
"""

import pytest

from aeris.exposure.exceptions import (
    APIRateLimitError,
    ConfigurationError,
    ExposureEstimatorError,
    GeocodingError,
    InputValidationError,
    UpstreamAPIError,
)

EXCEPTION_CLASSES = [
    ConfigurationError,
    InputValidationError,
    GeocodingError,
    APIRateLimitError,
    UpstreamAPIError,
]


class TestExceptionHierarchy:
    """Test that all custom exceptions form a proper hierarchy."""

    @pytest.mark.parametrize("exc_cls", EXCEPTION_CLASSES)
    def test_subclass_of_base(self, exc_cls):
        assert issubclass(exc_cls, ExposureEstimatorError)

    @pytest.mark.parametrize("exc_cls", EXCEPTION_CLASSES)
    def test_subclass_of_builtin_exception(self, exc_cls):
        assert issubclass(exc_cls, Exception)

    @pytest.mark.parametrize("exc_cls", EXCEPTION_CLASSES)
    def test_can_instantiate_with_message(self, exc_cls):
        err = exc_cls("test message")
        assert str(err) == "test message"

    @pytest.mark.parametrize("exc_cls", EXCEPTION_CLASSES)
    def test_catchable_by_base(self, exc_cls):
        with pytest.raises(ExposureEstimatorError):
            raise exc_cls("caught by base")

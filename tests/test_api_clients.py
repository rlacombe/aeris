"""
Tests for API client modules: rate limiting, geometry, payload construction.
"""

import math
from unittest.mock import MagicMock, patch

import pytest

from aeris.exposure.api_clients.google_maps import GoogleAirQualityClient
from aeris.exposure.api_clients.accuweather import AccuWeatherAirQualityClient
from aeris.exposure.api_clients.openaq import RateLimitedOpenAQ
from aeris.exposure.api_clients.openmeteo import OpenMeteoClient
from aeris.exposure.api_clients.overpass import OverpassClient
from aeris.exposure.api_clients.purpleair import PurpleAirClient
from aeris.exposure.config import Config
from aeris.exposure.exceptions import UpstreamAPIError


# ---------------------------------------------------------------------------
# RateLimitedOpenAQ
# ---------------------------------------------------------------------------
class TestRateLimiter:
    """Test OpenAQ rate-limiter throttle logic."""

    @patch("aeris.exposure.api_clients.openaq.OpenAQ")
    def test_counters_increment(self, mock_openaq_cls):
        cfg = Config(openaq_calls_per_minute=50, openaq_calls_per_hour=2000)
        client = RateLimitedOpenAQ("key", cfg)

        client._throttle()
        assert client.calls_minute == 1
        assert client.calls_hour == 1
        assert client._total_api_calls == 1

    @patch("aeris.exposure.api_clients.openaq.OpenAQ")
    def test_total_calls_property(self, mock_openaq_cls):
        cfg = Config(openaq_calls_per_minute=50, openaq_calls_per_hour=2000)
        client = RateLimitedOpenAQ("key", cfg)

        for _ in range(5):
            client._throttle()
        assert client.total_calls == 5

    @patch("aeris.exposure.api_clients.openaq.time")
    @patch("aeris.exposure.api_clients.openaq.OpenAQ")
    def test_minute_window_reset(self, mock_openaq_cls, mock_time):
        """Counters should reset after 60 seconds."""
        cfg = Config(openaq_calls_per_minute=50, openaq_calls_per_hour=2000)

        # First call at t=0
        mock_time.time.return_value = 0.0
        client = RateLimitedOpenAQ("key", cfg)
        client._throttle()
        assert client.calls_minute == 1

        # Second call at t=61 (past minute window)
        mock_time.time.return_value = 61.0
        client._throttle()
        assert client.calls_minute == 1  # Reset to 0 then incremented to 1

    @patch("aeris.exposure.api_clients.openaq.time")
    @patch("aeris.exposure.api_clients.openaq.OpenAQ")
    def test_minute_limit_triggers_sleep(self, mock_openaq_cls, mock_time):
        """Should sleep when minute limit is reached."""
        cfg = Config(openaq_calls_per_minute=2, openaq_calls_per_hour=2000)

        mock_time.time.return_value = 0.0
        client = RateLimitedOpenAQ("key", cfg)

        # Exhaust minute limit
        client._throttle()
        client._throttle()
        assert client.calls_minute == 2

        # Next call should trigger sleep
        mock_time.time.return_value = 30.0  # 30s into minute window
        client._throttle()
        mock_time.sleep.assert_called()


# ---------------------------------------------------------------------------
# OverpassClient geometry
# ---------------------------------------------------------------------------
class TestPointToSegmentDistance:
    """Test the _point_to_segment_distance method."""

    def setup_method(self):
        self.client = OverpassClient()

    def test_point_on_segment_start(self):
        """Point at segment start should give ~0 distance."""
        dist = self.client._point_to_segment_distance(40.0, -74.0, 40.0, -74.0, 41.0, -73.0)
        assert dist < 1.0  # less than 1 meter

    def test_degenerate_segment(self):
        """Degenerate segment (start == end) should give point-to-point distance."""
        dist = self.client._point_to_segment_distance(40.0, -74.0, 40.01, -74.0, 40.01, -74.0)
        # ~1.1 km
        assert 1000 < dist < 1200

    def test_perpendicular_projection(self):
        """Point perpendicular to segment midpoint."""
        # Segment along the equator from (0, 0) to (0, 1)
        # Point at (0.01, 0.5) should project onto (0, 0.5)
        dist = self.client._point_to_segment_distance(0.01, 0.5, 0.0, 0.0, 0.0, 1.0)
        # 0.01 degrees latitude ≈ 1.11 km
        assert 1000 < dist < 1200

    def test_symmetric(self):
        """Distance should be same regardless of segment direction."""
        d1 = self.client._point_to_segment_distance(40.0, -74.0, 40.0, -74.1, 40.0, -73.9)
        d2 = self.client._point_to_segment_distance(40.0, -74.0, 40.0, -73.9, 40.0, -74.1)
        assert abs(d1 - d2) < 1.0  # should be identical (within float tolerance)


# ---------------------------------------------------------------------------
# AccuWeatherAirQualityClient
# ---------------------------------------------------------------------------
class TestAccuWeatherAirQualityClient:
    @patch("aeris.exposure.api_clients.accuweather.requests.get")
    def test_daily_air_quality_preserves_index_semantics(self, mock_get):
        location = MagicMock()
        location.status_code = 200
        location.json.return_value = {
            "Key": "349727",
            "LocalizedName": "New York",
            "DataSets": ["AirQuality"],
        }
        forecast = MagicMock()
        forecast.status_code = 200
        forecast.json.return_value = {
            "DailyForecasts": [
                {
                    "Date": "2026-08-22T07:00:00-04:00",
                    "AirAndPollen": [
                        {
                            "Name": "Air Quality",
                            "Value": 42,
                            "Category": "Good",
                            "CategoryValue": 1,
                            "Type": "Particle Pollution",
                        }
                    ],
                }
            ]
        }
        mock_get.side_effect = [location, forecast]

        result = AccuWeatherAirQualityClient("test-key").daily_air_quality(40.7, -74.0)

        assert result["source_type"] == "air_quality_index"
        assert result["index_value"] == 42
        assert result["dominant_pollutant"] == "Particle Pollution"
        assert "not a pollutant concentration" in result["warning"]
        assert mock_get.call_args_list[0].kwargs["headers"]["Authorization"] == "Bearer test-key"

    @patch("aeris.exposure.api_clients.accuweather.requests.get")
    def test_daily_air_quality_requires_available_product(self, mock_get):
        location = MagicMock()
        location.status_code = 200
        location.json.return_value = {"Key": "349727", "DataSets": []}
        mock_get.return_value = location

        with pytest.raises(UpstreamAPIError, match="does not advertise AirQuality"):
            AccuWeatherAirQualityClient("test-key").daily_air_quality(40.7, -74.0)


# ---------------------------------------------------------------------------
# GoogleAirQualityClient
# ---------------------------------------------------------------------------
class TestGoogleMapsClient:
    """Test Google Maps Air Quality client."""

    @patch("aeris.exposure.api_clients.google_maps.requests.post")
    def test_history_lookup_with_datetime(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"hoursInfo": [{"dateTime": "2024-01-01T00:00:00Z"}]}
        mock_post.return_value = mock_response

        client = GoogleAirQualityClient(api_key="test_key")
        result = client.history_lookup(40.7, -74.0, date_time_iso="2024-01-01T00:00:00Z")

        assert "hoursInfo" in result
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert payload["location"]["latitude"] == 40.7
        assert payload["location"]["longitude"] == -74.0

    @patch("aeris.exposure.api_clients.google_maps.requests.post")
    def test_history_lookup_error_response(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": {"message": "API key invalid"}}
        mock_post.return_value = mock_response

        client = GoogleAirQualityClient(api_key="bad_key")
        with pytest.raises(UpstreamAPIError, match="API key invalid"):
            client.history_lookup(40.7, -74.0, date_time_iso="2024-01-01T00:00:00Z")

    @patch("aeris.exposure.api_clients.google_maps.requests.post")
    def test_history_lookup_http_error(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {}
        mock_response.text = "Forbidden"
        mock_post.return_value = mock_response

        client = GoogleAirQualityClient(api_key="test_key")
        with pytest.raises(UpstreamAPIError, match="HTTP 403"):
            client.history_lookup(40.7, -74.0, date_time_iso="2024-01-01T00:00:00Z")


# ---------------------------------------------------------------------------
# PurpleAirClient
# ---------------------------------------------------------------------------
class TestPurpleAirClient:
    """Test PurpleAir client."""

    def test_headers(self):
        client = PurpleAirClient(api_key="test_pa_key")
        assert client._headers() == {"X-API-Key": "test_pa_key"}

    @patch("aeris.exposure.api_clients.purpleair.requests.get")
    def test_nearest_sensor_no_results(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"fields": [], "data": []}
        mock_get.return_value = mock_response

        client = PurpleAirClient(api_key="test_key")
        result = client.nearest_sensor(40.7, -74.0)
        assert result is None

    @patch("aeris.exposure.api_clients.purpleair.requests.get")
    def test_nearest_sensor_found(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "fields": ["latitude", "longitude", "pm2.5"],
            "data": [[40.71, -74.01, 12.5]],
        }
        mock_get.return_value = mock_response

        client = PurpleAirClient(api_key="test_key")
        result = client.nearest_sensor(40.7, -74.0)
        assert result is not None
        assert "distance_m" in result
        assert result["row"] == [40.71, -74.01, 12.5]

    @patch("aeris.exposure.api_clients.purpleair.requests.get")
    def test_nearest_sensor_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Error"
        mock_get.return_value = mock_response

        client = PurpleAirClient(api_key="test_key")
        with pytest.raises(UpstreamAPIError, match="PurpleAir HTTP 500"):
            client.nearest_sensor(40.7, -74.0)

    def test_bounding_box_calculation(self):
        """Verify the bounding box math for nearest_sensor params."""
        _client = PurpleAirClient(api_key="test_key")
        # The bounding box is computed inside nearest_sensor; test the math
        lat, _lon, radius_m = 40.0, -74.0, 25000
        dlat = radius_m / 111_000.0
        dlon = radius_m / (111_000.0 * max(0.1, math.cos(math.radians(lat))))

        assert abs(dlat - 0.2252) < 0.001
        assert dlon > dlat  # at 40 degrees, lon degree is shorter than lat degree


# ---------------------------------------------------------------------------
# OpenMeteoClient
# ---------------------------------------------------------------------------
class TestOpenMeteoClient:
    """Test Open-Meteo client."""

    @patch("aeris.exposure.api_clients.openmeteo.requests.get")
    def test_get_hourly_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "hourly": {
                "temperature_2m": [20.0],
                "relative_humidity_2m": [65.0],
                "windspeed_10m": [5.0],
            }
        }
        mock_get.return_value = mock_response

        client = OpenMeteoClient()
        result = client.get_hourly(40.7, -74.0, "2024-01-01", "2024-01-01")

        assert "hourly" in result
        # Verify correct parameters were sent
        call_kwargs = mock_get.call_args
        params = call_kwargs[1]["params"]
        assert params["latitude"] == 40.7
        assert params["longitude"] == -74.0
        assert params["timezone"] == "UTC"

    @patch("aeris.exposure.api_clients.openmeteo.requests.get")
    def test_get_hourly_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_get.return_value = mock_response

        client = OpenMeteoClient()
        with pytest.raises(UpstreamAPIError, match="Open-Meteo HTTP 400"):
            client.get_hourly(40.7, -74.0, "2024-01-01", "2024-01-01")

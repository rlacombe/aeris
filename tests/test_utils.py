"""
Tests for utility functions.
"""

from unittest.mock import patch

import pandas as pd
import pytest

from aeris.exposure.exceptions import GeocodingError
from aeris.exposure.utils import (
    calculate_metrics,
    concentration_to_aqi,
    flag_outliers,
    geocode_address,
    geocode_zip,
    haversine,
    idw_average,
    pretty_pollutant,
    time_weighted_mean,
)


class TestHaversine:
    """Test haversine distance calculation."""

    def test_haversine_same_point(self):
        """Test distance between same point is zero."""
        distance = haversine(40.7128, -74.0060, 40.7128, -74.0060)
        assert distance == 0.0

    def test_haversine_known_distance(self):
        """Test distance calculation for known coordinates."""
        # Distance between NYC and LA (approximately)
        nyc_lat, nyc_lon = 40.7128, -74.0060
        la_lat, la_lon = 34.0522, -118.2437

        distance = haversine(nyc_lat, nyc_lon, la_lat, la_lon)

        # Should be approximately 3944 km
        assert 3900 < distance / 1000 < 4000

    def test_haversine_short_distance(self):
        """Test distance calculation for short distances."""
        # Distance between two nearby points in NYC
        lat1, lon1 = 40.7128, -74.0060
        lat2, lon2 = 40.7138, -74.0070

        distance = haversine(lat1, lon1, lat2, lon2)

        # Should be approximately 100-200 meters
        assert 50 < distance < 300


class TestPrettyPollutant:
    """Test pollutant name formatting."""

    def test_pretty_pollutant_pm25(self):
        """Test PM2.5 formatting."""
        result = pretty_pollutant("pm25")
        assert result == "PM$_{2.5}$"

    def test_pretty_pollutant_pm10(self):
        """Test PM10 formatting."""
        result = pretty_pollutant("pm10")
        assert result == "PM$_{10}$"

    def test_pretty_pollutant_gases(self):
        """Test gas pollutant formatting."""
        assert pretty_pollutant("so2") == "SO$_2$"
        assert pretty_pollutant("no2") == "NO$_2$"
        assert pretty_pollutant("co") == "CO"
        assert pretty_pollutant("o3") == "O$_3$"

    def test_pretty_pollutant_case_insensitive(self):
        """Test formatting is case insensitive."""
        assert pretty_pollutant("PM25") == "PM$_{2.5}$"
        assert pretty_pollutant("PM25") == pretty_pollutant("pm25")

    def test_pretty_pollutant_unknown(self):
        """Test unknown pollutant returns uppercase."""
        result = pretty_pollutant("unknown")
        assert result == "UNKNOWN"


_EMPTY_METRICS = {
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


class TestCalculateMetrics:
    """Test metrics calculation."""

    def test_calculate_metrics_empty_data(self):
        """Test metrics calculation with empty data."""
        df = pd.DataFrame()
        result = calculate_metrics(df, "pm25")
        assert result == _EMPTY_METRICS

    def test_calculate_metrics_none_data(self):
        """Test metrics calculation with None data."""
        result = calculate_metrics(None, "pm25")
        assert result == _EMPTY_METRICS

    def test_calculate_metrics_valid_data(self):
        """Test metrics calculation with valid data."""
        data = {
            "timestamp_utc": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
            "value": [10.5, 12.3],
            "parameter": ["pm25", "pm25"],
        }
        df = pd.DataFrame(data)

        result = calculate_metrics(df, "pm25")

        assert result["mean"] == 11.4
        assert result["median"] == 11.4
        assert result["n_samples"] == 2
        assert result["std"] is not None
        assert result["min"] == 10.5
        assert result["max"] == 12.3
        assert result["p25"] is not None
        assert result["p75"] is not None

    def test_calculate_metrics_with_period_column(self):
        """Test metrics calculation with period column format."""
        data = {
            "period": [
                {"datetime_from": {"utc": "2024-01-01T00:00:00Z"}},
                {"datetime_from": {"utc": "2024-01-01T01:00:00Z"}},
            ],
            "value": [10.5, 12.3],
            "parameter": ["pm25", "pm25"],
        }
        df = pd.DataFrame(data)

        result = calculate_metrics(df, "pm25")

        assert result["mean"] == 11.4
        assert result["n_samples"] == 2

    def test_calculate_metrics_wrong_pollutant(self):
        """Test metrics calculation with wrong pollutant filter."""
        data = {"timestamp_utc": ["2024-01-01T00:00:00Z"], "value": [10.5], "parameter": ["pm25"]}
        df = pd.DataFrame(data)

        result = calculate_metrics(df, "pm10")  # Wrong pollutant
        assert result == _EMPTY_METRICS

    def test_calculate_metrics_mixed_parameters(self):
        """Test metrics calculation with mixed parameter formats."""
        data = {
            "timestamp_utc": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
            "value": [10.5, 12.3],
            "parameter": [
                {"name": "pm25"},  # Dict format
                "pm25",  # String format
            ],
        }
        df = pd.DataFrame(data)

        result = calculate_metrics(df, "pm25")

        assert result["mean"] == 11.4
        assert result["n_samples"] == 2


class TestCalculateMetricsCompleteness:
    """Test completeness_pct in calculate_metrics."""

    def _make_df(self, values):
        return pd.DataFrame(
            {
                "timestamp_utc": [f"2024-01-01T{i:02d}:00:00Z" for i in range(len(values))],
                "value": values,
                "parameter": ["pm25"] * len(values),
            }
        )

    def test_completeness_with_expected_hours(self):
        """completeness_pct is present when expected_hours is given."""
        df = self._make_df([5.0, 10.0])
        result = calculate_metrics(df, "pm25", expected_hours=10)
        assert result["completeness_pct"] == 20.0

    def test_completeness_100_percent(self):
        """100% completeness when samples match expected hours."""
        df = self._make_df([5.0, 10.0])
        result = calculate_metrics(df, "pm25", expected_hours=2)
        assert result["completeness_pct"] == 100.0

    def test_completeness_absent_without_expected_hours(self):
        """completeness_pct is absent when expected_hours is not given."""
        df = self._make_df([5.0, 10.0])
        result = calculate_metrics(df, "pm25")
        assert "completeness_pct" not in result

    def test_completeness_zero_samples(self):
        """completeness_pct is absent for empty data (no samples)."""
        df = pd.DataFrame()
        result = calculate_metrics(df, "pm25", expected_hours=24)
        assert "completeness_pct" not in result


class TestGeocoding:
    """Test geocoding functions."""

    def test_geocode_zip_valid(self):
        """Test geocoding valid ZIP code."""
        # Using a known ZIP code (10001 - Manhattan, NYC)
        lat, lon = geocode_zip("10001")

        assert isinstance(lat, float)
        assert isinstance(lon, float)
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180
        # Should be in NYC area
        assert 40.0 < lat < 41.0
        assert -75.0 < lon < -73.0

    def test_geocode_zip_international(self):
        """Test geocoding with country parameter (French postal code)."""
        # Use "fr" which pgeocode likely already has cached or is more reliable
        lat, lon = geocode_zip("75001", country="fr")
        assert isinstance(lat, float)
        assert isinstance(lon, float)
        # Should be in Paris area
        assert 48.0 < lat < 49.0
        assert 2.0 < lon < 3.0

    def test_geocode_zip_invalid(self):
        """Test geocoding invalid ZIP code."""
        with pytest.raises(GeocodingError):
            geocode_zip("99999")

    @patch("aeris.exposure.utils.requests.get")
    def test_geocode_address_valid(self, request):
        """Test geocoding valid address."""
        request.return_value.status_code = 200
        request.return_value.json.return_value = [{"lat": "40.758", "lon": "-73.9855"}]
        lat, lon = geocode_address("Times Square, New York, NY")

        assert isinstance(lat, float)
        assert isinstance(lon, float)
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180
        # Should be in NYC area
        assert 40.0 < lat < 41.0
        assert -75.0 < lon < -73.0

    @patch("aeris.exposure.utils.requests.get")
    def test_geocode_address_invalid(self, request):
        """Test geocoding invalid address."""
        request.return_value.status_code = 200
        request.return_value.json.return_value = []
        with pytest.raises(GeocodingError):
            geocode_address("ThisIsNotARealAddress12345XYZ")


class TestCalculateMetricsExceedance:
    """Test exceedance counting in calculate_metrics."""

    def _make_df(self, values):
        return pd.DataFrame(
            {
                "timestamp_utc": [f"2024-01-01T{i:02d}:00:00Z" for i in range(len(values))],
                "value": values,
                "parameter": ["pm25"] * len(values),
            }
        )

    def test_exceedance_with_threshold(self):
        """Exceedance keys present when threshold is given."""
        df = self._make_df([5.0, 15.0, 25.0, 35.0])
        result = calculate_metrics(df, "pm25", threshold=20.0)

        assert result["exceedance_count"] == 2
        assert result["exceedance_pct"] == 50.0
        assert result["exceedance_threshold"] == 20.0

    def test_exceedance_none_without_threshold(self):
        """Exceedance keys absent when no threshold is given."""
        df = self._make_df([5.0, 15.0])
        result = calculate_metrics(df, "pm25")
        assert "exceedance_count" not in result

    def test_exceedance_all_below(self):
        """Zero exceedances when all values are below threshold."""
        df = self._make_df([1.0, 2.0, 3.0])
        result = calculate_metrics(df, "pm25", threshold=10.0)
        assert result["exceedance_count"] == 0
        assert result["exceedance_pct"] == 0.0

    def test_exceedance_all_above(self):
        """All values exceed threshold."""
        df = self._make_df([50.0, 60.0])
        result = calculate_metrics(df, "pm25", threshold=10.0)
        assert result["exceedance_count"] == 2
        assert result["exceedance_pct"] == 100.0


class TestCalculateMetricsPercentiles:
    """Test percentile accuracy in calculate_metrics."""

    def test_percentiles_known_distribution(self):
        """Test percentiles on a range of values."""
        values = list(range(1, 101))  # 1 to 100
        df = pd.DataFrame(
            {
                "timestamp_utc": [
                    f"2024-01-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(100)
                ],
                "value": values,
                "parameter": ["pm25"] * 100,
            }
        )
        result = calculate_metrics(df, "pm25")
        assert result["min"] == 1.0
        assert result["max"] == 100.0
        assert abs(result["p5"] - 5.95) < 1.0
        assert abs(result["p25"] - 25.75) < 1.0
        assert abs(result["p75"] - 75.25) < 1.0
        assert abs(result["p95"] - 95.05) < 1.0


class TestAQIConversion:
    """Test EPA AQI conversion."""

    def test_pm25_good(self):
        aqi, cat = concentration_to_aqi(5.0, "pm25")
        assert 0 <= aqi <= 50
        assert cat == "Good"

    def test_pm25_moderate(self):
        aqi, cat = concentration_to_aqi(20.0, "pm25")
        assert 51 <= aqi <= 100
        assert cat == "Moderate"

    def test_pm10(self):
        aqi, cat = concentration_to_aqi(50, "pm10")
        assert 0 <= aqi <= 50
        assert cat == "Good"

    def test_no2(self):
        aqi, cat = concentration_to_aqi(40, "no2")
        assert 0 <= aqi <= 50
        assert cat == "Good"

    def test_co(self):
        aqi, cat = concentration_to_aqi(2.0, "co")
        assert 0 <= aqi <= 50
        assert cat == "Good"

    def test_so2(self):
        aqi, cat = concentration_to_aqi(30, "so2")
        assert 0 <= aqi <= 50
        assert cat == "Good"

    def test_o3(self):
        aqi, cat = concentration_to_aqi(0.04, "o3")
        assert 0 <= aqi <= 50
        assert cat == "Good"

    def test_boundary_value(self):
        """Test exact boundary (PM2.5 = 9.0 should be AQI 50)."""
        aqi, cat = concentration_to_aqi(9.0, "pm25")
        assert aqi == 50
        assert cat == "Good"

    def test_unhealthy_range(self):
        """Test unhealthy PM2.5 range."""
        aqi, cat = concentration_to_aqi(100.0, "pm25")
        assert 151 <= aqi <= 200
        assert cat == "Unhealthy"

    def test_unknown_pollutant(self):
        with pytest.raises(ValueError, match="Unknown pollutant"):
            concentration_to_aqi(10.0, "xyz")

    def test_out_of_range(self):
        with pytest.raises(ValueError, match="exceeds AQI breakpoint"):
            concentration_to_aqi(999.0, "pm25")

    def test_case_insensitive(self):
        aqi1, _ = concentration_to_aqi(5.0, "pm25")
        aqi2, _ = concentration_to_aqi(5.0, "PM25")
        assert aqi1 == aqi2


class TestFlagOutliers:
    """Test outlier detection."""

    def test_removes_negative_values(self):
        vals = pd.Series([10.0, -5.0, 20.0, 15.0])
        clean, n = flag_outliers(vals)
        assert -5.0 not in clean.values
        assert n >= 1

    def test_removes_iqr_outliers(self):
        vals = pd.Series([10.0, 11.0, 12.0, 10.5, 11.5, 100.0])
        clean, n = flag_outliers(vals)
        assert 100.0 not in clean.values
        assert n >= 1

    def test_no_outliers(self):
        vals = pd.Series([10.0, 11.0, 12.0, 10.5, 11.5])
        clean, n = flag_outliers(vals)
        assert n == 0
        assert len(clean) == 5

    def test_keep_negative_when_disabled(self):
        """With enough spread, a mild negative isn't an IQR outlier."""
        vals = pd.Series([-1.0, 0.0, 5.0, 10.0, 15.0, 20.0, 25.0])
        clean, _ = flag_outliers(vals, remove_negative=False)
        assert -1.0 in clean.values


class TestTimeWeightedMean:
    """Test time-weighted average."""

    def test_uniform_spacing(self):
        """With uniform 1-hour gaps, TWM should equal arithmetic mean."""
        ts = pd.to_datetime(
            ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z", "2024-01-01T02:00:00Z"], utc=True
        )
        vals = pd.Series([10.0, 20.0, 30.0])
        result = time_weighted_mean(ts, vals)
        assert result is not None
        assert abs(result - 20.0) < 0.1

    def test_non_uniform_spacing(self):
        """With a large gap, the isolated point gets less weight."""
        ts = pd.to_datetime(
            ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z", "2024-01-01T10:00:00Z"], utc=True
        )
        vals = pd.Series([10.0, 10.0, 100.0])
        result = time_weighted_mean(ts, vals)
        assert result is not None
        # The 100.0 value at T10 has a large left half-interval,
        # so TWM should be higher than arithmetic mean of ~40
        assert result > 20.0

    def test_single_value(self):
        ts = pd.to_datetime(["2024-01-01T00:00:00Z"], utc=True)
        vals = pd.Series([42.0])
        assert time_weighted_mean(ts, vals) == 42.0

    def test_empty_returns_none(self):
        ts = pd.to_datetime([], utc=True)
        vals = pd.Series([], dtype=float)
        assert time_weighted_mean(ts, vals) is None


class TestIDWAverage:
    """Test inverse-distance-weighted averaging."""

    def test_single_station(self):
        result = idw_average([10.0], [1000.0])
        assert result == 10.0

    def test_two_stations_equal_distance(self):
        result = idw_average([10.0, 20.0], [1000.0, 1000.0])
        assert result == 15.0

    def test_closer_station_weighted_more(self):
        result = idw_average([10.0, 20.0], [100.0, 1000.0])
        assert result is not None
        # Station at 100m (value 10) should dominate
        assert result < 15.0

    def test_zero_distance(self):
        """Co-located station returns its value directly."""
        result = idw_average([42.0, 20.0], [0.0, 1000.0])
        assert result == 42.0

    def test_empty_returns_none(self):
        assert idw_average([], []) is None

    def test_none_values_skipped(self):
        result = idw_average([None, 20.0], [500.0, 1000.0])
        assert result == 20.0


class TestIDWHourlySeries:
    """Test hour-aligned IDW exposure series."""

    def _station_frame(self, hours_values, parameter="pm25", unit="µg/m³"):
        rows = []
        for hour, value in hours_values:
            rows.append(
                {
                    "timestamp_utc": pd.Timestamp(hour, tz="UTC"),
                    "value": value,
                    "parameter": parameter,
                    "unit": unit,
                }
            )
        return pd.DataFrame(rows)

    def test_identical_stations(self):
        """Equal distances and values → IDW equals that value."""
        from aeris.exposure.utils import idw_hourly_series

        a = self._station_frame([("2023-01-01 00:00", 10.0), ("2023-01-01 01:00", 12.0)])
        b = self._station_frame([("2023-01-01 00:00", 10.0), ("2023-01-01 01:00", 12.0)])
        out = idw_hourly_series([a, b], [1000.0, 1000.0], "pm25")
        assert len(out) == 2
        assert abs(out.loc[0, "value"] - 10.0) < 1e-9
        assert abs(out.loc[1, "value"] - 12.0) < 1e-9
        assert out.loc[0, "n_stations_hour"] == 2

    def test_closer_station_dominates(self):
        from aeris.exposure.utils import idw_hourly_series

        a = self._station_frame([("2023-01-01 00:00", 10.0)])
        b = self._station_frame([("2023-01-01 00:00", 20.0)])
        out = idw_hourly_series([a, b], [100.0, 1000.0], "pm25")
        assert len(out) == 1
        assert out.loc[0, "value"] < 15.0

    def test_missing_hour_at_one_station(self):
        """Hour with only one station still gets a value."""
        from aeris.exposure.utils import idw_hourly_series

        a = self._station_frame([("2023-01-01 00:00", 10.0), ("2023-01-01 01:00", 11.0)])
        b = self._station_frame([("2023-01-01 00:00", 20.0)])  # missing hour 1
        out = idw_hourly_series([a, b], [1000.0, 1000.0], "pm25")
        assert len(out) == 2
        assert out.loc[out["timestamp_utc"] == pd.Timestamp("2023-01-01 01:00", tz="UTC"), "value"].iloc[
            0
        ] == 11.0
        assert (
            out.loc[
                out["timestamp_utc"] == pd.Timestamp("2023-01-01 01:00", tz="UTC"), "n_stations_hour"
            ].iloc[0]
            == 1
        )

    def test_empty_inputs(self):
        from aeris.exposure.utils import idw_hourly_series

        out = idw_hourly_series([], [], "pm25")
        assert out.empty

    def test_mismatched_lengths(self):
        from aeris.exposure.utils import idw_hourly_series

        a = self._station_frame([("2023-01-01 00:00", 10.0)])
        out = idw_hourly_series([a], [1000.0, 2000.0], "pm25")
        assert out.empty


class TestGeocodingCache:
    """Test that geocoding lru_cache works."""

    def test_geocode_zip_cache_hit(self):
        """Second call to same ZIP returns cached result."""
        geocode_zip.cache_clear()
        r1 = geocode_zip("10001")
        r2 = geocode_zip("10001")
        assert r1 == r2
        info = geocode_zip.cache_info()
        assert info.hits >= 1

    def test_geocode_zip_different_calls(self):
        """Different ZIPs are cached separately."""
        geocode_zip.cache_clear()
        r1 = geocode_zip("10001")
        r2 = geocode_zip("90001")
        assert r1 != r2
        info = geocode_zip.cache_info()
        assert info.misses >= 2


class TestCalculateMetricsOutlierDetection:
    """Test outlier detection in calculate_metrics."""

    def _make_df(self, values):
        return pd.DataFrame(
            {
                "timestamp_utc": [f"2024-01-01T{i:02d}:00:00Z" for i in range(len(values))],
                "value": values,
                "parameter": ["pm25"] * len(values),
            }
        )

    def test_outlier_detection_removes_negatives(self):
        df = self._make_df([10.0, -5.0, 12.0, 11.0])
        result = calculate_metrics(df, "pm25", outlier_detection=True)
        assert result["n_outliers_removed"] >= 1
        assert result["mean"] > 0

    def test_outlier_detection_off_by_default(self):
        df = self._make_df([10.0, -5.0, 12.0])
        result = calculate_metrics(df, "pm25")
        assert "n_outliers_removed" not in result


class TestCalculateMetricsTimeWeighted:
    """Test time-weighted mean in calculate_metrics."""

    def test_time_weighted_mean_present(self):
        data = {
            "timestamp_utc": [
                "2024-01-01T00:00:00Z",
                "2024-01-01T01:00:00Z",
                "2024-01-01T02:00:00Z",
            ],
            "value": [10.0, 20.0, 30.0],
            "parameter": ["pm25"] * 3,
        }
        df = pd.DataFrame(data)
        result = calculate_metrics(df, "pm25")
        assert "time_weighted_mean" in result
        assert abs(result["time_weighted_mean"] - 20.0) < 0.1

    def test_time_weighted_mean_absent_single_value(self):
        data = {
            "timestamp_utc": ["2024-01-01T00:00:00Z"],
            "value": [10.0],
            "parameter": ["pm25"],
        }
        df = pd.DataFrame(data)
        result = calculate_metrics(df, "pm25")
        # Only 1 timestamp, so tw mean won't be computed (needs >= 2)
        assert "time_weighted_mean" not in result

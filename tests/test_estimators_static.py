"""
Tests for the static mode estimator (ExposureEstimatorOpenAQStatic).
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from aeris.exposure.config import Config
from aeris.exposure.cache import ResponseCache
from aeris.exposure.estimators.static import ExposureEstimatorOpenAQStatic
from aeris.exposure.exceptions import ConfigurationError


def _make_config(**overrides):
    """Create a Config with a valid OpenAQ key and optional overrides."""
    defaults = {"openaq_api_key": "test_key"}
    defaults.update(overrides)
    return Config(**defaults)


class TestStaticInit:
    """Test ExposureEstimatorOpenAQStatic initialization."""

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_valid_init(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm25",
            config=_make_config(),
        )
        assert est.pollutant == "pm25"

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_pollutant_is_lowered(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="PM25",
            config=_make_config(),
        )
        assert est.pollutant == "pm25"

    def test_invalid_pollutant_raises(self):
        with pytest.raises(ConfigurationError, match="Invalid pollutant"):
            ExposureEstimatorOpenAQStatic(
                input_csv="data.csv",
                pollutant="invalid",
                config=_make_config(),
            )

    def test_missing_api_key_raises(self):
        with pytest.raises(ConfigurationError, match="Missing OpenAQ API key"):
            ExposureEstimatorOpenAQStatic(
                input_csv="data.csv",
                pollutant="pm25",
                config=Config(),
            )

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_api_key_override(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm25",
            api_key="override_key",
            config=Config(),
        )
        assert est.config.openaq_api_key == "override_key"

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_search_radius_is_explicit_and_bounded(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv", pollutant="pm10", config=_make_config(),
            search_radius_km=50,
        )
        assert est.search_radius_m == 50_000
        with pytest.raises(ConfigurationError, match="at most 200"):
            ExposureEstimatorOpenAQStatic(
                input_csv="data.csv", pollutant="pm10", config=_make_config(),
                search_radius_km=250,
            )

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_complete_catalog_empty_result_does_not_call_radius_api(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv", pollutant="pm10", config=_make_config(),
            search_radius_km=50,
        )
        est._catalog_locations = []
        est._catalog_used = True

        assert est._nearby_stations(37.31, 13.58) == []
        mock_client.return_value.list_locations.assert_not_called()

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_large_radius_without_complete_catalog_fails_clearly(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv", pollutant="pm10", config=_make_config(),
            search_radius_km=50,
        )

        with pytest.raises(ConfigurationError, match="complete country location catalog"):
            est._nearby_stations(37.31, 13.58)
        mock_client.return_value.list_locations.assert_not_called()

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_nearest_complete_station_skips_incomplete_candidate(self, mock_client, monkeypatch):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv", pollutant="pm10", config=_make_config(),
            min_completeness=75, temporal_resolution="daily",
        )
        est.df_input = pd.DataFrame({
            "subject_id": ["city"], "latitude": [45.0], "longitude": [9.0],
            "start_dt": [pd.Timestamp("2018-01-01")],
            "end_dt": [pd.Timestamp("2018-01-04")],
        })
        sensor1 = SimpleNamespace(id=101, parameter=SimpleNamespace(name="pm10", units="ug/m3"))
        sensor2 = SimpleNamespace(id=202, parameter=SimpleNamespace(name="pm10", units="ug/m3"))
        locations = [
            SimpleNamespace(id=1, name="near", coordinates={"latitude": 45.01, "longitude": 9.0}, sensors=[sensor1]),
            SimpleNamespace(id=2, name="complete", coordinates={"latitude": 45.02, "longitude": 9.0}, sensors=[sensor2]),
        ]
        monkeypatch.setattr(est, "_load_location_catalog", lambda: None)
        monkeypatch.setattr(est, "_nearby_stations", lambda lat, lon, *_dates: locations)

        def records(sensor_id, *_args):
            days = ["2018-01-01"] if sensor_id == 101 else [
                "2018-01-01", "2018-01-02", "2018-01-03", "2018-01-04"
            ]
            return [{
                "value": 20.0,
                "parameter": {"name": "pm10", "units": "ug/m3"},
                "period": {"datetime_from": {"utc": f"{day}T12:00:00Z"}},
            } for day in days]

        monkeypatch.setattr(est, "_fetch_sensor_data", records)
        result = pd.DataFrame(est._run_static(raw_output=False))

        assert result.loc[0, "station_id"] == 2
        assert result.loc[0, "n_stations_rejected_incomplete"] == 1
        assert result.loc[0, "n_stations_screened"] == 2

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_multiple_complete_stations_produce_idw_result(self, mock_client, monkeypatch):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv", pollutant="pm10", config=_make_config(),
            n_stations=2, temporal_resolution="daily",
        )
        est.df_input = pd.DataFrame({
            "subject_id": ["city"], "latitude": [45.0], "longitude": [9.0],
            "start_dt": [pd.Timestamp("2018-01-01")],
            "end_dt": [pd.Timestamp("2018-01-02")],
        })
        sensors = [
            SimpleNamespace(id=101, parameter=SimpleNamespace(name="pm10", units="ug/m3")),
            SimpleNamespace(id=202, parameter=SimpleNamespace(name="pm10", units="ug/m3")),
        ]
        locations = [
            SimpleNamespace(id=index, name=f"station-{index}",
                            coordinates={"latitude": 45.0 + index / 100, "longitude": 9.0},
                            sensors=[sensor])
            for index, sensor in enumerate(sensors, start=1)
        ]
        monkeypatch.setattr(est, "_load_location_catalog", lambda: None)
        monkeypatch.setattr(est, "_nearby_stations", lambda lat, lon, *_dates: locations)
        monkeypatch.setattr(est, "_fetch_sensor_data", lambda *_args: [
            {"value": 20.0, "parameter": {"name": "pm10", "units": "ug/m3"},
             "period": {"datetime_from": {"utc": f"{day}T12:00:00Z"}}}
            for day in ("2018-01-01", "2018-01-02")
        ])

        result = pd.DataFrame(est._run_static(raw_output=False))

        assert len(result) == 1
        assert result.loc[0, "n_stations_idw"] == 2

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_catalog_excludes_locations_outside_requested_period(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv", pollutant="pm10", config=_make_config(),
            location_strategy="catalog", search_radius_km=200,
        )
        sensor = SimpleNamespace(id=101, parameter=SimpleNamespace(name="pm10", units="ug/m3"))
        est._catalog_locations = [
            SimpleNamespace(
                id=1, coordinates={"latitude": 45.0, "longitude": 9.0}, sensors=[sensor],
                datetime_first={"utc": "2020-01-01T00:00:00Z"},
                datetime_last={"utc": "2024-12-31T00:00:00Z"},
            ),
            SimpleNamespace(
                id=2, coordinates={"latitude": 45.1, "longitude": 9.0}, sensors=[sensor],
                datetime_first={"utc": "2017-01-01T00:00:00Z"},
                datetime_last={"utc": "2019-12-31T00:00:00Z"},
            ),
        ]
        est._catalog_used = True

        stations = est._nearby_stations(
            45.0, 9.0, pd.Timestamp("2018-01-01"), pd.Timestamp("2019-01-01")
        )

        assert [station.id for station in stations] == [2]

    @patch("aeris.exposure.estimators.static.geocode_address")
    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_geocoding_is_retained_in_run_cache(self, mock_client, mock_geocode, tmp_path):
        cache = ResponseCache(db_path=str(tmp_path / "cache.sqlite"))
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm25",
            config=_make_config(),
            cache=cache,
        )
        mock_geocode.return_value = (51.5, -0.12)
        row = SimpleNamespace(address="London, United Kingdom", zip=None)

        assert est._geocode_row(row) == (51.5, -0.12)
        assert est._geocode_row(row) == (51.5, -0.12)
        mock_geocode.assert_called_once_with("London, United Kingdom")
        cache.close()

    @patch("aeris.exposure.estimators.static.OpenAQArchiveClient")
    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_empty_v3_series_uses_bounded_archive_fallback(self, mock_client, mock_archive):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm10",
            config=_make_config(),
            temporal_resolution="daily",
        )
        mock_client.return_value.list_daily_measurements.return_value = MagicMock(results=[])
        archive_rows = [
            {
                "value": 12.0,
                "parameter": {"name": "pm10", "units": "ug/m3"},
                "period": {"datetime_from": {"utc": "2020-03-01T12:00:00Z"}},
                "source": "openaq_archive_s3",
            }
        ]
        mock_archive.return_value.fetch_daily_range_checkpointed.return_value = archive_rows

        rows = est._fetch_sensor_data(
            999,
            2178,
            "pm10",
            pd.Timestamp("2020-03-01", tz="UTC").to_pydatetime(),
            pd.Timestamp("2020-03-02", tz="UTC").to_pydatetime(),
            "2020-03-01T00:00:00Z",
            "2020-03-02T00:00:00Z",
        )

        assert rows == archive_rows
        mock_archive.return_value.fetch_daily_range_checkpointed.assert_called_once()

    @patch("aeris.exposure.estimators.static.OpenAQArchiveClient")
    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_static_fills_missing_v3_days_from_archive(self, mock_client, mock_archive):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm10",
            config=_make_config(),
            temporal_resolution="daily",
        )
        mock_client.return_value.list_daily_measurements.return_value = MagicMock(
            results=[
                {
                    "value": 10.0,
                    "parameter": {"name": "pm10", "units": "ug/m3"},
                    "period": {"datetime_from": {"utc": "2020-03-01T12:00:00Z"}},
                }
            ]
        )
        mock_archive.return_value.fetch_daily_range_checkpointed.return_value = [
            {
                "value": 20.0,
                "parameter": {"name": "pm10", "units": "ug/m3"},
                "period": {"datetime_from": {"utc": "2020-03-02T12:00:00Z"}},
                "source": "openaq_archive_s3",
            }
        ]

        rows = est._fetch_sensor_data(
            999,
            2178,
            "pm10",
            pd.Timestamp("2020-03-01", tz="UTC").to_pydatetime(),
            pd.Timestamp("2020-03-03", tz="UTC").to_pydatetime(),
            "2020-03-01T00:00:00Z",
            "2020-03-03T00:00:00Z",
        )

        assert [row["value"] for row in rows] == [10.0, 20.0]
        mock_archive.return_value.fetch_daily_range_checkpointed.assert_called_once()


class TestEstimateApiCalls:
    """Test API call estimation logic."""

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_single_subject_one_day(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm25",
            config=_make_config(),
        )
        est.df_input = pd.DataFrame(
            {
                "subject_id": ["S001"],
                "start_dt": [pd.Timestamp("2024-01-01")],
                "end_dt": [pd.Timestamp("2024-01-01")],
            }
        )

        calls, _minutes, _hours = est.estimate_api_calls()
        # 1 day = 24 hours, ceil(24/1000) = 1 page, so 1 + 1 = 2 calls
        assert calls == 2

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_single_subject_long_range(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm25",
            config=_make_config(),
        )
        est.df_input = pd.DataFrame(
            {
                "subject_id": ["S001"],
                "start_dt": [pd.Timestamp("2024-01-01")],
                "end_dt": [pd.Timestamp("2024-03-01")],  # 61 days
            }
        )

        calls, _minutes, _hours = est.estimate_api_calls()
        # 61 days * 24 = 1464 hours, ceil(1464/1000) = 2 pages, so 1 + 2 = 3 calls
        assert calls == 3

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_daily_resolution_uses_daily_page_count(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm25",
            config=_make_config(),
            temporal_resolution="daily",
        )
        est.df_input = pd.DataFrame(
            {
                "subject_id": ["S001"],
                "start_dt": [pd.Timestamp("2021-01-01")],
                "end_dt": [pd.Timestamp("2023-12-31")],
            }
        )

        calls, _minutes, _hours = est.estimate_api_calls()
        # 1,095 daily aggregates fit in two 1,000-row pages, plus discovery.
        assert calls == 3

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_catalog_plan_replaces_per_subject_discovery_upper_bound(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm25",
            config=_make_config(),
            country="cn",
            temporal_resolution="daily",
            location_strategy="catalog",
        )
        est.df_input = pd.DataFrame(
            {
                "subject_id": [str(i) for i in range(25)],
                "start_dt": [pd.Timestamp("2021-01-01")] * 25,
                "end_dt": [pd.Timestamp("2021-01-01")] * 25,
            }
        )

        calls, _minutes, _hours = est.estimate_api_calls()
        # 25 direct discovery calls are replaced by at most ten catalog pages.
        assert calls == 35

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_raises_if_input_not_loaded(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm25",
            config=_make_config(),
        )
        with pytest.raises(RuntimeError, match="read_and_validate_input"):
            est.estimate_api_calls()


class TestTidyRawDf:
    """Test the static method _tidy_raw_df."""

    def test_dict_format(self):
        """Test with dict-style parameter (raw JSON-like response)."""
        rows = pd.DataFrame(
            {
                "period": [
                    {"datetime_from": {"utc": "2024-01-01T00:00:00Z"}},
                    {"datetime_from": {"utc": "2024-01-01T01:00:00Z"}},
                ],
                "value": [10.5, 12.3],
                "parameter": [
                    {"name": "pm25", "units": "µg/m³"},
                    {"name": "pm25", "units": "µg/m³"},
                ],
            }
        )
        result = ExposureEstimatorOpenAQStatic._tidy_raw_df(rows)
        assert list(result.columns) == ["timestamp_utc", "value", "parameter", "unit", "data_source"]
        assert len(result) == 2
        assert result["parameter"].iloc[0] == "pm25"
        assert result["value"].iloc[0] == 10.5
        assert result["data_source"].tolist() == ["openaq_v3", "openaq_v3"]

    def test_json_string_period(self):
        """Test with JSON-string period (serialized format)."""
        period_str = json.dumps({"datetime_from": {"utc": "2024-01-01T00:00:00Z"}})
        rows = pd.DataFrame(
            {
                "period": [period_str],
                "value": [15.0],
                "parameter": [{"name": "no2", "units": "ppb"}],
            }
        )
        result = ExposureEstimatorOpenAQStatic._tidy_raw_df(rows)
        assert len(result) == 1
        assert result["timestamp_utc"].iloc[0] == "2024-01-01T00:00:00Z"

    def test_sorted_by_timestamp(self):
        """Test that output is sorted by timestamp."""
        rows = pd.DataFrame(
            {
                "period": [
                    {"datetime_from": {"utc": "2024-01-01T02:00:00Z"}},
                    {"datetime_from": {"utc": "2024-01-01T00:00:00Z"}},
                    {"datetime_from": {"utc": "2024-01-01T01:00:00Z"}},
                ],
                "value": [1.0, 2.0, 3.0],
                "parameter": [{"name": "pm25"}] * 3,
            }
        )
        result = ExposureEstimatorOpenAQStatic._tidy_raw_df(rows)
        assert list(result["timestamp_utc"]) == [
            "2024-01-01T00:00:00Z",
            "2024-01-01T01:00:00Z",
            "2024-01-01T02:00:00Z",
        ]


class TestExtractUnit:
    """Test the static method _extract_unit."""

    def test_unit_from_dataframe_column(self):
        dfm = pd.DataFrame({"unit": ["µg/m³", "µg/m³"]})
        sensor = MagicMock()
        assert ExposureEstimatorOpenAQStatic._extract_unit(dfm, sensor) == "µg/m³"

    def test_unit_from_sensor_attr(self):
        dfm = pd.DataFrame({"other": [1]})  # no 'unit' column
        sensor = MagicMock()
        sensor.parameter.units = "ppb"
        assert ExposureEstimatorOpenAQStatic._extract_unit(dfm, sensor) == "ppb"

    def test_unit_from_sensor_list(self):
        dfm = pd.DataFrame({"other": [1]})
        sensor = MagicMock()
        sensor.parameter.units = ["µg/m³", "ppb"]
        assert ExposureEstimatorOpenAQStatic._extract_unit(dfm, sensor) == "µg/m³"

    def test_returns_none_when_unavailable(self):
        dfm = pd.DataFrame({"other": [1]})
        sensor = MagicMock()
        sensor.parameter.units = None
        assert ExposureEstimatorOpenAQStatic._extract_unit(dfm, sensor) is None

    def test_unit_column_all_nan(self):
        dfm = pd.DataFrame({"unit": [None, None]})
        sensor = MagicMock()
        sensor.parameter.units = "ppb"
        assert ExposureEstimatorOpenAQStatic._extract_unit(dfm, sensor) == "ppb"


class TestGetRawData:
    """Test get_raw_data method."""

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_returns_all_subjects(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm25",
            config=_make_config(),
        )
        est._per_subject_tidy = {
            "S001": [
                pd.DataFrame(
                    {
                        "timestamp_utc": ["2024-01-01T00:00:00Z"],
                        "value": [10.0],
                        "parameter": ["pm25"],
                        "unit": ["µg/m³"],
                    }
                )
            ],
            "S002": [
                pd.DataFrame(
                    {
                        "timestamp_utc": ["2024-01-01T00:00:00Z"],
                        "value": [15.0],
                        "parameter": ["pm25"],
                        "unit": ["µg/m³"],
                    }
                )
            ],
        }

        result = est.get_raw_data()
        assert len(result) == 2
        assert set(result["subject_id"].unique()) == {"S001", "S002"}

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_filters_by_subject(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm25",
            config=_make_config(),
        )
        est._per_subject_tidy = {
            "S001": [
                pd.DataFrame(
                    {
                        "timestamp_utc": ["2024-01-01T00:00:00Z"],
                        "value": [10.0],
                        "parameter": ["pm25"],
                        "unit": ["µg/m³"],
                    }
                )
            ],
            "S002": [
                pd.DataFrame(
                    {
                        "timestamp_utc": ["2024-01-01T00:00:00Z"],
                        "value": [15.0],
                        "parameter": ["pm25"],
                        "unit": ["µg/m³"],
                    }
                )
            ],
        }

        result = est.get_raw_data(subject_id="S001")
        assert len(result) == 1
        assert result["subject_id"].iloc[0] == "S001"

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_raises_before_run(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm25",
            config=_make_config(),
        )
        est._per_subject_tidy = {}
        with pytest.raises(RuntimeError, match="Must call run"):
            est.get_raw_data()


class TestGetDailyData:
    """Test get_daily_data method."""

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_daily_aggregation(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm25",
            config=_make_config(),
        )
        est._per_subject_tidy = {
            "S001": [
                pd.DataFrame(
                    {
                        "timestamp_utc": [
                            "2024-01-01T00:00:00Z",
                            "2024-01-01T06:00:00Z",
                            "2024-01-01T12:00:00Z",
                            "2024-01-02T00:00:00Z",
                        ],
                        "value": [10.0, 20.0, 30.0, 5.0],
                        "parameter": ["pm25"] * 4,
                        "unit": ["µg/m³"] * 4,
                    }
                )
            ],
        }

        result = est.get_daily_data()
        assert len(result) == 2  # 2 dates
        assert "mean" in result.columns
        assert "min" in result.columns
        assert "max" in result.columns
        assert "count" in result.columns

    @patch("aeris.exposure.estimators.static.RateLimitedOpenAQ")
    def test_custom_agg_functions(self, mock_client):
        est = ExposureEstimatorOpenAQStatic(
            input_csv="data.csv",
            pollutant="pm25",
            config=_make_config(),
        )
        est._per_subject_tidy = {
            "S001": [
                pd.DataFrame(
                    {
                        "timestamp_utc": ["2024-01-01T00:00:00Z", "2024-01-01T06:00:00Z"],
                        "value": [10.0, 20.0],
                        "parameter": ["pm25"] * 2,
                        "unit": ["µg/m³"] * 2,
                    }
                )
            ],
        }

        result = est.get_daily_data(agg_functions=["mean", "std", "median"])
        assert "mean" in result.columns
        assert "std" in result.columns
        assert "median" in result.columns
        assert "min" not in result.columns  # not requested

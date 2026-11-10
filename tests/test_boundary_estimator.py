from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from shapely.geometry import Polygon

from aeris.exposure.boundaries import AdministrativeBoundary, boundary_from_geojson
from aeris.exposure.config import Config
from aeris.exposure.estimators.boundary import ExposureEstimatorOpenAQBoundary
from aeris.exposure.exceptions import InputValidationError


def _boundary():
    return AdministrativeBoundary(
        name="Test area",
        geometry=Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        source="test",
        metadata={},
    )


def test_geojson_requires_feature_name_for_multiple_boundaries(tmp_path):
    path = tmp_path / "boundaries.geojson"
    path.write_text(
        '{"type":"FeatureCollection","features":['
        '{"type":"Feature","properties":{"name":"A"},"geometry":{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,0]]]}},'
        '{"type":"Feature","properties":{"name":"B"},"geometry":{"type":"Polygon","coordinates":[[[2,2],[3,2],[3,3],[2,2]]]}}]}'
    )

    with pytest.raises(InputValidationError, match="multiple features"):
        boundary_from_geojson(path)

    assert boundary_from_geojson(path, "B").name == "B"


@patch("aeris.exposure.estimators.boundary.RateLimitedOpenAQ")
def test_boundary_estimator_uses_only_monitors_inside_polygon(mock_client):
    sensor_one = SimpleNamespace(id=101, parameter=SimpleNamespace(name="pm25", units="ug/m3"))
    sensor_two = SimpleNamespace(id=102, parameter=SimpleNamespace(name="pm25", units="ug/m3"))
    inside_one = SimpleNamespace(
        id=1,
        name="Inside one",
        coordinates={"latitude": 0.25, "longitude": 0.25},
        sensors=[sensor_one],
    )
    inside_two = SimpleNamespace(
        id=2,
        name="Inside two",
        coordinates={"latitude": 0.75, "longitude": 0.75},
        sensors=[sensor_two],
    )
    outside = SimpleNamespace(
        id=3,
        name="Outside",
        coordinates={"latitude": 1.25, "longitude": 1.25},
        sensors=[sensor_one],
    )
    late = SimpleNamespace(
        id=4,
        name="Too late",
        coordinates={"latitude": 0.5, "longitude": 0.5},
        sensors=[sensor_one],
        datetimeFirst={"utc": "2024-02-01T00:00:00Z"},
    )
    client = mock_client.return_value
    client.list_locations.return_value = SimpleNamespace(
        results=[inside_one, inside_two, outside, late]
    )
    client.list_measurements.side_effect = [
        SimpleNamespace(
            results=[
                {
                    "period": {"datetime_from": {"utc": "2024-01-01T00:00:00Z"}},
                    "value": 10.0,
                    "parameter": {"name": "pm25", "units": "ug/m3"},
                }
            ]
        ),
        SimpleNamespace(
            results=[
                {
                    "period": {"datetime_from": {"utc": "2024-01-01T00:00:00Z"}},
                    "value": 20.0,
                    "parameter": {"name": "pm25", "units": "ug/m3"},
                }
            ]
        ),
    ]

    estimator = ExposureEstimatorOpenAQBoundary(
        boundary=_boundary(),
        start_date="2024-01-01",
        end_date="2024-01-01",
        pollutant="pm25",
        config=Config(openaq_api_key="test-key"),
        min_completeness=50,
    )
    result = estimator.run().iloc[0]

    assert client.list_locations.call_args.kwargs["bbox"] == (0.0, 0.0, 1.0, 1.0)
    assert result["mean"] == 15.0
    assert result["n_stations"] == 2
    assert result["aggregation"] == "unweighted_mean_of_station_means"
    assert estimator.get_station_info()["location_id"].tolist() == [1, 2]
    daily = estimator.get_daily_data()
    assert daily.to_dict(orient="records") == [
        {"date": "2024-01-01", "unit": "ug/m3", "mean": 15.0, "n_stations": 2, "n_hourly_observations": 2}
    ]


@patch("aeris.exposure.estimators.boundary.RateLimitedOpenAQ")
def test_boundary_station_budget_is_deterministic_and_reported(mock_client):
    sensor = SimpleNamespace(id=101, parameter=SimpleNamespace(name="pm25", units="ug/m3"))
    locations = [
        SimpleNamespace(
            id=index,
            name=f"Station {index}",
            coordinates={"latitude": latitude, "longitude": longitude},
            sensors=[SimpleNamespace(id=100 + index, parameter=sensor.parameter)],
        )
        for index, (latitude, longitude) in enumerate(
            [(0.5, 0.5), (0.05, 0.05), (0.05, 0.95), (0.95, 0.05), (0.95, 0.95)],
            start=1,
        )
    ]
    client = mock_client.return_value
    client.list_locations.return_value = SimpleNamespace(results=list(reversed(locations)))
    client.list_measurements.side_effect = [
        SimpleNamespace(results=[{
            "period": {"datetime_from": {"utc": "2024-01-01T00:00:00Z"}},
            "value": float(index), "parameter": {"name": "pm25", "units": "ug/m3"},
        }])
        for index in range(3)
    ]
    estimator = ExposureEstimatorOpenAQBoundary(
        boundary=_boundary(), start_date="2024-01-01", end_date="2024-01-01",
        pollutant="pm25", config=Config(openaq_api_key="test-key"), max_stations=3,
    )

    selected = estimator.discover_stations()
    assert [row["location_id"] for row in selected] == [1, 2, 5]
    result = estimator.run().iloc[0]
    assert result["n_stations_available"] == 5
    assert result["max_stations"] == 3
    assert result["station_selection"] == "deterministic_spatial_spread"


@patch("aeris.exposure.estimators.boundary.OpenAQArchiveClient")
@patch("aeris.exposure.estimators.boundary.RateLimitedOpenAQ")
def test_boundary_uses_archive_after_empty_v3_series(mock_client, mock_archive):
    client = mock_client.return_value
    client.list_daily_measurements.return_value = MagicMock(results=[])
    archive_rows = [
        {
            "value": 16.0,
            "parameter": {"name": "pm10", "units": "ug/m3"},
            "period": {"datetime_from": {"utc": "2020-03-01T12:00:00Z"}},
            "source": "openaq_archive_s3",
        }
    ]
    mock_archive.return_value.fetch_daily_range_checkpointed.return_value = archive_rows
    estimator = ExposureEstimatorOpenAQBoundary(
        boundary=_boundary(),
        start_date="2020-03-01",
        end_date="2020-03-01",
        pollutant="pm10",
        config=Config(openaq_api_key="test-key"),
    )

    data = estimator._fetch_sensor_hours({"location_id": 2178, "sensor_id": 99})

    assert data["value"].tolist() == [16.0]
    mock_archive.return_value.fetch_daily_range_checkpointed.assert_called_once()


@patch("aeris.exposure.estimators.boundary.OpenAQArchiveClient")
@patch("aeris.exposure.estimators.boundary.RateLimitedOpenAQ")
def test_boundary_fills_missing_v3_days_from_archive(mock_client, mock_archive):
    client = mock_client.return_value
    client.list_daily_measurements.return_value = MagicMock(
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
            "value": 10.0,
            "parameter": {"name": "pm10", "units": "ug/m3"},
            "period": {"datetime_from": {"utc": "2020-03-01T12:00:00Z"}},
            "source": "openaq_archive_s3",
        },
        {
            "value": 20.0,
            "parameter": {"name": "pm10", "units": "ug/m3"},
            "period": {"datetime_from": {"utc": "2020-03-02T12:00:00Z"}},
            "source": "openaq_archive_s3",
        },
    ]
    estimator = ExposureEstimatorOpenAQBoundary(
        boundary=_boundary(),
        start_date="2020-03-01",
        end_date="2020-03-02",
        pollutant="pm10",
        config=Config(openaq_api_key="test-key"),
        temporal_resolution="daily",
    )

    data = estimator._fetch_sensor_hours({"location_id": 2178, "sensor_id": 99})

    assert data["value"].tolist() == [10.0, 20.0]
    assert data["data_source"].tolist() == ["openaq_v3", "openaq_archive_s3"]
    mock_archive.return_value.fetch_daily_range_checkpointed.assert_called_once()

"""Focused tests for the unsigned OpenAQ archive client."""

import gzip
from datetime import date
from unittest.mock import MagicMock

import pytest
import requests

from aeris.exposure.api_clients.openaq_archive import OpenAQArchiveClient
from aeris.exposure.exceptions import UpstreamAPIError


def _gzip_csv(text: str) -> bytes:
    return gzip.compress(text.encode("utf-8"))


def _response(status_code: int, body: bytes = b"", text: str = "error") -> MagicMock:
    response = MagicMock(status_code=status_code, text=text)
    response.iter_content.return_value = [body]
    return response


class TestOpenAQArchiveClient:
    def test_object_url_uses_documented_partition_and_filename_layout(self):
        assert OpenAQArchiveClient.object_url(2178, date(2022, 5, 3)) == (
            "https://openaq-data-archive.s3.amazonaws.com/records/csv.gz/"
            "locationid=2178/year=2022/month=05/location-2178-20220503.csv.gz"
        )

    def test_fetch_day_decompresses_and_filters_sensor_and_parameter(self):
        request = MagicMock(
            return_value=_response(
                200,
                _gzip_csv(
                    "location_id,sensor_id,parameter,value\n"
                    "2178,3919,pm10,14.0\n2178,3919,pm25,8.0\n2178,4000,pm10,9.0\n"
                ),
            )
        )
        client = OpenAQArchiveClient(request=request)

        rows = client.fetch_day(2178, date(2022, 5, 3), sensor_id=3919, parameter="pm10")

        assert rows == [{"location_id": "2178", "sensor_id": "3919", "parameter": "pm10", "value": "14.0"}]
        request.assert_called_once_with(
            "https://openaq-data-archive.s3.amazonaws.com/records/csv.gz/"
            "locationid=2178/year=2022/month=05/location-2178-20220503.csv.gz",
            stream=True,
            timeout=(3.05, 30.0),
        )

    def test_retries_transient_request_failures(self):
        request = MagicMock(
            side_effect=[requests.Timeout("slow"), _response(200, _gzip_csv("parameter,value\npm10,1\n"))]
        )
        sleep = MagicMock()
        client = OpenAQArchiveClient(request=request, sleep=sleep, max_retries=1, retry_backoff=0.5)

        assert client.fetch_day(2178, date(2022, 5, 3)) == [{"parameter": "pm10", "value": "1"}]
        assert request.call_count == 2
        sleep.assert_called_once_with(0.5)

    def test_does_not_retry_non_retryable_http_error(self):
        request = MagicMock(return_value=_response(404, text="missing"))
        client = OpenAQArchiveClient(request=request, max_retries=2)

        with pytest.raises(UpstreamAPIError, match="HTTP 404"):
            client.fetch_day(2178, date(2022, 5, 3))
        request.assert_called_once()

    def test_rejects_payloads_that_exceed_compressed_limit(self):
        request = MagicMock(return_value=_response(200, b"x" * 11))
        client = OpenAQArchiveClient(request=request, max_download_bytes=10)

        with pytest.raises(UpstreamAPIError, match="download exceeds"):
            client.fetch_day(2178, date(2022, 5, 3))

    def test_rejects_payloads_that_exceed_decompressed_limit(self):
        request = MagicMock(return_value=_response(200, _gzip_csv("x" * 100)))
        client = OpenAQArchiveClient(request=request, max_decompressed_bytes=10)

        with pytest.raises(UpstreamAPIError, match="decompressed data exceeds"):
            client.fetch_day(2178, date(2022, 5, 3))

    def test_fetch_daily_range_uses_parameter_not_current_sensor_id(self):
        csv_body = _gzip_csv(
            "location_id,sensors_id,datetime,parameter,units,value\n"
            "2178,99,2020-03-01T01:00:00+01:00,pm10,ug/m3,10\n"
            "2178,99,2020-03-01T02:00:00+01:00,pm10,ug/m3,14\n"
            "2178,100,2020-03-01T02:00:00+01:00,no2,ug/m3,20\n"
        )
        request = MagicMock(return_value=_response(200, csv_body))
        client = OpenAQArchiveClient(request=request)

        rows = client.fetch_daily_range(
            2178,
            date(2020, 3, 1),
            date(2020, 3, 2),
            parameter="pm10",
            available_dates=[date(2020, 3, 1)],
        )

        assert rows == [
            {
                "value": 12.0,
                "parameter": {"name": "pm10", "units": "ug/m3"},
                "period": {"datetime_from": {"utc": "2020-03-01T12:00:00Z"}},
                "source": "openaq_archive_s3",
            }
        ]

    def test_checkpointed_range_retries_only_incomplete_chunks(self):
        cache = MagicMock()
        cache.get.side_effect = [None, [{"value": 3.0}]]
        cache_rows = [{"value": 1.0}]
        client = OpenAQArchiveClient()
        client.fetch_daily_range = MagicMock(return_value=cache_rows)

        rows = client.fetch_daily_range_checkpointed(
            2178,
            parameter="pm25",
            available_dates=[date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3)],
            chunk_size=2,
            cache=cache,
        )

        assert rows == [{"value": 1.0}, {"value": 3.0}]
        client.fetch_daily_range.assert_called_once()
        cache.put.assert_called_once()

    def test_checkpointed_range_does_not_cache_partial_chunk(self):
        client = OpenAQArchiveClient()
        cache = MagicMock()
        cache.get.return_value = None

        def partial(*args, **kwargs):
            client.last_errors = ["2020-01-02: timeout"]
            return [{"value": 1.0}]

        client.fetch_daily_range = MagicMock(side_effect=partial)
        rows = client.fetch_daily_range_checkpointed(
            2178, parameter="pm25", available_dates=[date(2020, 1, 1), date(2020, 1, 2)],
            chunk_size=2, cache=cache,
        )

        assert rows == [{"value": 1.0}]
        assert client.last_errors == ["2020-01-02: timeout"]
        cache.put.assert_not_called()

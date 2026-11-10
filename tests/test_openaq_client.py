from types import SimpleNamespace
from unittest.mock import patch

import pytest

from aeris.exposure.api_clients.openaq import (
    MAX_RETRIES,
    RATE_LIMIT_FALLBACK_SECONDS,
    RateLimitedOpenAQ,
)
from aeris.exposure.config import Config


class HTTPError(Exception):
    def __init__(self, status_code, headers=None):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        self.headers = headers


def make_client(mock_openaq_cls):
    return RateLimitedOpenAQ("key", Config(openaq_calls_per_minute=50, openaq_calls_per_hour=2000))


@patch("aeris.exposure.api_clients.openaq.time")
@patch("aeris.exposure.api_clients.openaq.OpenAQ")
def test_waits_for_server_reset_before_next_request(mock_openaq_cls, mock_time):
    mock_time.time.return_value = 100.0
    client = make_client(mock_openaq_cls)
    result = SimpleNamespace(headers=SimpleNamespace(x_ratelimit_remaining=0, x_ratelimit_reset=30))
    mock_openaq_cls.return_value.locations.list.return_value = result

    assert client.list_locations() is result
    assert client.list_locations() is result

    mock_time.sleep.assert_called_once_with(30.0)
    assert client.total_calls == 2


@patch("aeris.exposure.api_clients.openaq.time")
@patch("aeris.exposure.api_clients.openaq.OpenAQ")
def test_interprets_absolute_reset_timestamp_without_oversleeping(mock_openaq_cls, mock_time):
    mock_time.time.return_value = 1_700_000_000.0
    client = make_client(mock_openaq_cls)
    result = SimpleNamespace(
        headers=SimpleNamespace(x_ratelimit_remaining=0, x_ratelimit_reset=1_700_000_030)
    )
    mock_openaq_cls.return_value.locations.list.return_value = result

    assert client.list_locations() is result
    assert client.list_locations() is result

    mock_time.sleep.assert_called_once_with(30.0)


@patch("aeris.exposure.api_clients.openaq.time")
@patch("aeris.exposure.api_clients.openaq.OpenAQ")
def test_uses_retry_after_for_rate_limited_request(mock_openaq_cls, mock_time):
    mock_time.time.return_value = 100.0
    client = make_client(mock_openaq_cls)
    expected = SimpleNamespace(headers={"X-RateLimit-Remaining": "8"})
    mock_openaq_cls.return_value.locations.list.side_effect = [
        HTTPError(429, {"Retry-After": "7"}),
        expected,
    ]

    assert client.list_locations(country_id=1) is expected

    mock_time.sleep.assert_called_once_with(7.0)
    assert client.total_calls == 2


@patch("aeris.exposure.api_clients.openaq.time")
@patch("aeris.exposure.api_clients.openaq.OpenAQ")
def test_uses_conservative_wait_for_rate_limit_without_header(mock_openaq_cls, mock_time):
    mock_time.time.return_value = 100.0
    client = make_client(mock_openaq_cls)
    expected = SimpleNamespace(headers={"X-RateLimit-Remaining": "8"})
    mock_openaq_cls.return_value.locations.list.side_effect = [HTTPError(429), expected]

    assert client.list_locations(country_id=1) is expected

    mock_time.sleep.assert_called_once_with(RATE_LIMIT_FALLBACK_SECONDS)


@patch("aeris.exposure.api_clients.openaq.time")
@patch("aeris.exposure.api_clients.openaq.OpenAQ")
def test_retries_server_errors_with_bounded_exponential_backoff(mock_openaq_cls, mock_time):
    mock_time.time.return_value = 100.0
    client = make_client(mock_openaq_cls)
    mock_openaq_cls.return_value.measurements.list.side_effect = HTTPError(503)

    with pytest.raises(HTTPError):
        client.list_measurements(sensors_id=1)

    assert mock_openaq_cls.return_value.measurements.list.call_count == MAX_RETRIES + 1
    assert mock_time.sleep.call_args_list == [
        ((1.0,),),
        ((2.0,),),
        ((4.0,),),
    ]


@patch("aeris.exposure.api_clients.openaq.time")
@patch("aeris.exposure.api_clients.openaq.OpenAQ")
def test_response_headers_update_server_budget(mock_openaq_cls, mock_time):
    mock_time.time.return_value = 100.0
    client = make_client(mock_openaq_cls)
    mock_openaq_cls.return_value.locations.list.side_effect = [
        SimpleNamespace(headers={"X-RateLimit-Remaining": "1", "X-RateLimit-Reset": "12"}),
        SimpleNamespace(headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "12"}),
        SimpleNamespace(headers={"X-RateLimit-Remaining": "4", "X-RateLimit-Reset": "12"}),
    ]

    client.list_locations()
    client.list_locations()
    client.list_locations()

    mock_time.sleep.assert_called_once_with(12.0)

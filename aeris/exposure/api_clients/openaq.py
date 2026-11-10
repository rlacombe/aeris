"""
OpenAQ API client with rate limiting.
"""

import logging
import time
from collections.abc import Callable, Mapping
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from openaq import OpenAQ
from openaq._sync.transport import Transport
from openaq.shared.responses import MeasurementsResponse
from openaq.shared.transport import check_response

from ..config import Config

logger = logging.getLogger(__name__)


MAX_RETRIES = 3
BACKOFF_SECONDS = 1.0
RATE_LIMIT_FALLBACK_SECONDS = 60.0


class _BoundedOpenAQTransport(Transport):
    """Use the SDK with an explicit timeout on every request.

    The SDK's default transport creates an ``httpx.Request`` directly before
    calling ``Client.send``.  That bypasses the client's configured timeout
    extensions, allowing a stalled upstream connection to wait indefinitely.
    ``Client.request`` builds the request through the client and retains the
    configured timeout.
    """

    def __init__(self) -> None:
        self.client = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))

    def send_request(
        self,
        method: str,
        url: str,
        params: httpx.QueryParams | Mapping[str, str | int | float | bool] | None,
        headers: httpx.Headers | Mapping[str, str],
    ) -> httpx.Response:
        return check_response(self.client.request(method, url, params=params, headers=headers))


class RateLimitedOpenAQ:
    """
    Rate-limited wrapper around OpenAQ client.
    """

    def __init__(self, api_key: str, config: Config):
        self.client = OpenAQ(api_key=api_key, _transport=_BoundedOpenAQTransport())
        self.config = config

        # Rate limiting state
        self.calls_minute = 0
        self.calls_hour = 0
        self.minute_window_start = time.time()
        self.hour_window_start = time.time()
        self._total_api_calls = 0
        self._server_remaining: int | None = None
        self._server_reset_at: float | None = None

    def _throttle(self) -> None:
        """Enforce rate limits with sleeps as needed."""
        now = time.time()

        if self._server_remaining == 0 and self._server_reset_at is not None:
            server_sleep = self._server_reset_at - now
            if server_sleep > 0:
                logger.info("OpenAQ rate limit exhausted; pausing %.1fs", server_sleep)
                time.sleep(server_sleep)
            self._server_remaining = None
            self._server_reset_at = None
            now = time.time()

        # Reset counters if windows have passed
        if now - self.minute_window_start >= 60:
            self.minute_window_start, self.calls_minute = now, 0
        if now - self.hour_window_start >= 3_600:
            self.hour_window_start, self.calls_hour = now, 0

        # Check minute limit
        if self.calls_minute >= self.config.openaq_calls_per_minute:
            sleep = 60 - (now - self.minute_window_start)
            logger.debug("Hit minute limit - pausing %.1fs", sleep)
            time.sleep(max(sleep, 0))
            self.minute_window_start, self.calls_minute = time.time(), 0

        # Check hour limit
        if self.calls_hour >= self.config.openaq_calls_per_hour:
            sleep = 3_600 - (now - self.hour_window_start)
            logger.warning("Hit hour limit - pausing %.1fs", sleep)
            time.sleep(max(sleep, 0))
            self.hour_window_start, self.calls_hour = time.time(), 0

        self.calls_minute += 1
        self.calls_hour += 1
        self._total_api_calls += 1

        if self._server_remaining is not None:
            self._server_remaining = max(self._server_remaining - 1, 0)

    @staticmethod
    def _header_value(headers: Any, name: str) -> str | int | float | None:
        """Read a header from mappings or the OpenAQ SDK response object."""
        if headers is None:
            return None
        if isinstance(headers, Mapping):
            for key, value in headers.items():
                if str(key).lower() == name.lower():
                    return value
            return None
        return getattr(headers, name.lower().replace("-", "_"), None)

    def _capture_rate_limit_headers(self, source: Any) -> None:
        """Record server-provided budget information when the SDK exposes it."""
        headers = getattr(source, "headers", source)
        remaining = self._header_value(headers, "x-ratelimit-remaining")
        reset = self._header_value(headers, "x-ratelimit-reset")

        try:
            self._server_remaining = int(remaining) if remaining is not None else None
        except (TypeError, ValueError):
            self._server_remaining = None

        try:
            reset_value = float(reset) if reset is not None else None
        except (TypeError, ValueError):
            reset_value = None
        if reset_value is None:
            self._server_reset_at = None
        elif reset_value > 86_400:
            # Providers use both reset-after seconds and Unix timestamps.
            # A large value is an absolute timestamp; accept milliseconds too.
            if reset_value > 10_000_000_000:
                reset_value /= 1_000
            self._server_reset_at = max(reset_value, time.time())
        else:
            self._server_reset_at = time.time() + max(reset_value, 0)

    def _exception_headers(self, exc: Exception) -> Any:
        response = getattr(exc, "response", None)
        return getattr(response, "headers", None) or getattr(exc, "headers", None)

    def _retry_delay(self, exc: Exception, attempt: int) -> float:
        headers = self._exception_headers(exc)
        retry_after = self._header_value(headers, "retry-after")
        if retry_after is not None:
            try:
                return max(float(retry_after), 0)
            except (TypeError, ValueError):
                try:
                    return max(parsedate_to_datetime(str(retry_after)).timestamp() - time.time(), 0)
                except (TypeError, ValueError, IndexError, OverflowError):
                    pass

        if self._server_remaining == 0 and self._server_reset_at is not None:
            return max(self._server_reset_at - time.time(), 0)
        if getattr(exc, "status_code", None) == 429:
            # OpenAQ does not always expose Retry-After. A one-minute pause is
            # deliberately conservative and avoids retry bursts on a shared key.
            return RATE_LIMIT_FALLBACK_SECONDS
        if "ratelimit" in type(exc).__name__.lower():
            # The SDK sometimes omits status_code and reports a zero reset.
            return RATE_LIMIT_FALLBACK_SECONDS
        return BACKOFF_SECONDS * (2**attempt)

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)
        return (
            status_code == 429
            or "ratelimit" in type(exc).__name__.lower()
            or (isinstance(status_code, int) and 500 <= status_code < 600)
        )

    def _request(self, request: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute an OpenAQ request with bounded, server-aware retries."""
        for attempt in range(MAX_RETRIES + 1):
            self._throttle()
            try:
                result = request(*args, **kwargs)
            except Exception as exc:
                headers = self._exception_headers(exc)
                if headers is not None:
                    self._capture_rate_limit_headers(headers)
                if not self._is_retryable(exc) or attempt == MAX_RETRIES:
                    raise

                delay = self._retry_delay(exc, attempt)
                logger.warning(
                    "OpenAQ request failed with HTTP %s; retrying in %.1fs (%d/%d)",
                    getattr(exc, "status_code", "unknown"),
                    delay,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(delay)
                continue

            self._capture_rate_limit_headers(result)
            return result

        raise RuntimeError("OpenAQ retry loop exited unexpectedly")

    def list_locations(self, **kwargs):
        """Rate-limited wrapper for list_locations."""
        return self._request(self.client.locations.list, **kwargs)

    def list_measurements(self, **kwargs):
        """Rate-limited wrapper for list_measurements."""
        return self._request(self.client.measurements.list, **kwargs)

    def list_daily_measurements(
        self, *, sensor_id: int, date_from: str, date_to: str, page: int = 1, limit: int = 1000
    ) -> MeasurementsResponse:
        """Fetch documented sensor-day aggregates with date filters.

        OpenAQ's Python SDK currently sends ``datetime_from``/``datetime_to``
        to ``/days``. That endpoint accepts ``date_from``/``date_to`` instead;
        the incorrect parameters are silently ignored by the API. Use the SDK's
        authenticated transport and response parser while sending the documented
        date parameters directly.
        """
        response = self._request(
            self.client._get,
            f"/sensors/{sensor_id}/days",
            params={"date_from": date_from, "date_to": date_to, "page": page, "limit": limit},
        )
        return MeasurementsResponse.read_response(response)

    @property
    def total_calls(self) -> int:
        """Total number of API calls made."""
        return self._total_api_calls

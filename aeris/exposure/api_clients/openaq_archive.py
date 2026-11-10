"""Client for OpenAQ's public, unsigned S3 measurement archive."""

import csv
import gzip
import io
import logging
import re
import time
from collections.abc import Collection, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from typing import Any, Callable, Optional, Union
from xml.etree import ElementTree

import requests

from ..exceptions import InputValidationError, UpstreamAPIError

logger = logging.getLogger(__name__)


class OpenAQArchiveClient:
    """Retrieve a single OpenAQ location-day archive object without AWS credentials."""

    BASE_URL = "https://openaq-data-archive.s3.amazonaws.com"
    RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})
    DEFAULT_TIMEOUT = (3.05, 30.0)
    DEFAULT_MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
    DEFAULT_MAX_DECOMPRESSED_BYTES = 100 * 1024 * 1024

    def __init__(
        self,
        *,
        timeout: Union[float, tuple[float, float]] = DEFAULT_TIMEOUT,
        max_retries: int = 4,
        retry_backoff: float = 0.5,
        max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
        max_decompressed_bytes: int = DEFAULT_MAX_DECOMPRESSED_BYTES,
        request: Callable[..., Any] = requests.get,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_retries < 0 or retry_backoff < 0:
            raise InputValidationError("max_retries and retry_backoff must be non-negative")
        if max_download_bytes <= 0 or max_decompressed_bytes <= 0:
            raise InputValidationError("download and decompression limits must be positive")

        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self.max_download_bytes = max_download_bytes
        self.max_decompressed_bytes = max_decompressed_bytes
        self._request = request
        self._sleep = sleep
        self.last_errors: list[str] = []

    @classmethod
    def object_url(cls, location_id: int, measurement_date: date) -> str:
        """Build the documented public URL for a location's daily CSV.gz object."""
        if not isinstance(location_id, int) or isinstance(location_id, bool) or location_id <= 0:
            raise InputValidationError("location_id must be a positive integer")
        if not isinstance(measurement_date, date):
            raise InputValidationError("measurement_date must be a datetime.date")

        day = measurement_date.strftime("%Y%m%d")
        return (
            f"{cls.BASE_URL}/records/csv.gz/locationid={location_id}"
            f"/year={measurement_date:%Y}/month={measurement_date:%m}"
            f"/location-{location_id}-{day}.csv.gz"
        )

    def fetch_day(
        self,
        location_id: int,
        measurement_date: date,
        *,
        sensor_id: Optional[int] = None,
        parameter: Optional[str] = None,
    ) -> list[dict[str, str]]:
        """Fetch one location-day and return rows matching optional sensor and parameter filters."""
        if sensor_id is not None and (not isinstance(sensor_id, int) or isinstance(sensor_id, bool)):
            raise InputValidationError("sensor_id must be an integer when provided")
        if parameter is not None and not parameter.strip():
            raise InputValidationError("parameter must be non-empty when provided")

        payload = self._download(self.object_url(location_id, measurement_date))
        return list(self._filtered_rows(payload, sensor_id=sensor_id, parameter=parameter))

    def list_available_dates(self, location_id: int, start_date: date, end_date: date) -> list[date]:
        """List existing public archive objects for a location and date range."""
        if end_date < start_date:
            raise InputValidationError("end_date must not be earlier than start_date")
        dates: list[date] = []
        for year in range(start_date.year, end_date.year + 1):
            prefix = f"records/csv.gz/locationid={location_id}/year={year}/"
            token: str | None = None
            while True:
                params = {"list-type": "2", "prefix": prefix, "max-keys": 1000}
                if token:
                    params["continuation-token"] = token
                try:
                    response = self._request(self.BASE_URL, params=params, timeout=self.timeout)
                except requests.RequestException as exc:
                    raise UpstreamAPIError(f"OpenAQ archive listing failed: {exc}") from exc
                if response.status_code != 200:
                    raise UpstreamAPIError(f"OpenAQ archive listing HTTP {response.status_code}: {response.text}")
                try:
                    root = ElementTree.fromstring(response.content)
                except ElementTree.ParseError as exc:
                    raise UpstreamAPIError("OpenAQ archive listing returned invalid XML") from exc
                namespace = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
                for key in root.findall("s3:Contents/s3:Key", namespace):
                    match = re.search(r"-(\d{8})\.csv\.gz$", key.text or "")
                    if match:
                        value = datetime.strptime(match.group(1), "%Y%m%d").date()
                        if start_date <= value <= end_date:
                            dates.append(value)
                truncated = root.findtext("s3:IsTruncated", default="false", namespaces=namespace)
                token = root.findtext("s3:NextContinuationToken", namespaces=namespace)
                if truncated.lower() != "true" or not token:
                    break
        return sorted(set(dates))

    def fetch_daily_range(
        self,
        location_id: int,
        start_date: date,
        end_date: date,
        *,
        parameter: str,
        max_workers: int = 8,
        available_dates: Collection[date] | None = None,
    ) -> list[dict[str, Any]]:
        """Return daily means from archive location-day objects for one pollutant.

        Historical archive rows use a location-day object layout and can retain
        sensor identifiers that differ from the current v3 location catalogue.
        Filtering by the documented pollutant name therefore avoids treating a
        current sensor identifier as historical provenance.
        """
        if end_date < start_date:
            raise InputValidationError("end_date must not be earlier than start_date")
        if max_workers < 1:
            raise InputValidationError("max_workers must be positive")

        values_by_day: dict[date, list[float]] = {}
        units_by_day: dict[date, str] = {}
        dates = (
            sorted(set(available_dates))
            if available_dates is not None
            else self.list_available_dates(location_id, start_date, end_date)
        )
        if not dates:
            self.last_errors = []
            return []

        def fetch_one(measurement_date: date) -> tuple[list[dict[str, str]], str | None]:
            try:
                return self.fetch_day(location_id, measurement_date, parameter=parameter), None
            except UpstreamAPIError as exc:
                # Archive object absence is normal for an unreported location-day.
                if "HTTP 404" in str(exc):
                    return [], None
                return [], f"{measurement_date.isoformat()}: {exc}"

        errors: list[str] = []
        with ThreadPoolExecutor(max_workers=min(max_workers, len(dates))) as executor:
            day_results = executor.map(fetch_one, dates)
            for rows, error in day_results:
                if error:
                    errors.append(error)
                    continue
                for row in rows:
                    try:
                        value = float(row["value"])
                        timestamp = datetime.fromisoformat(row["datetime"].replace("Z", "+00:00"))
                    except (KeyError, TypeError, ValueError):
                        continue
                    local_day = timestamp.date()
                    values_by_day.setdefault(local_day, []).append(value)
                    units_by_day.setdefault(local_day, row.get("units", row.get("unit", "")))

        self.last_errors = errors
        if errors:
            logger.warning(
                "OpenAQ archive could not retrieve %d location-day objects for location %s.",
                len(errors),
                location_id,
            )

        results: list[dict[str, Any]] = []
        for measurement_day in sorted(values_by_day):
            values = values_by_day[measurement_day]
            results.append(
                {
                    "value": sum(values) / len(values),
                    "parameter": {"name": parameter, "units": units_by_day[measurement_day]},
                    # Noon UTC preserves the provider-local calendar date when
                    # downstream daily panels are grouped by timestamp.
                    "period": {
                        "datetime_from": {
                            "utc": datetime.combine(
                                measurement_day, datetime.min.time(), tzinfo=timezone.utc
                            ).replace(hour=12).isoformat().replace("+00:00", "Z")
                        }
                    },
                    "source": "openaq_archive_s3",
                }
            )
        return results

    def fetch_daily_range_checkpointed(
        self,
        location_id: int,
        *,
        parameter: str,
        available_dates: Collection[date],
        chunk_size: int,
        cache: Any | None = None,
        cache_namespace: str = "location_archive_daily_chunk_v1",
    ) -> list[dict[str, Any]]:
        """Fetch an arbitrary window as repairable, cached object chunks."""
        if chunk_size < 1:
            raise InputValidationError("chunk_size must be positive")
        dates = sorted(set(available_dates))
        rows: list[dict[str, Any]] = []
        all_errors: list[str] = []
        for offset in range(0, len(dates), chunk_size):
            chunk = dates[offset : offset + chunk_size]
            cache_key = {
                "endpoint": cache_namespace,
                "location_id": location_id,
                "parameter": parameter,
                "date_from": chunk[0].isoformat(),
                "date_to": chunk[-1].isoformat(),
                "object_count": len(chunk),
            }
            chunk_rows = cache.get(**cache_key) if cache else None
            if chunk_rows is None:
                chunk_rows = self.fetch_daily_range(
                    location_id,
                    chunk[0],
                    chunk[-1],
                    parameter=parameter,
                    available_dates=chunk,
                )
                chunk_errors = list(self.last_errors)
                all_errors.extend(chunk_errors)
                # A partial chunk is deliberately left uncached so the next run repairs it.
                if cache and not chunk_errors:
                    cache.put(chunk_rows, **cache_key)
            rows.extend(chunk_rows)
        self.last_errors = all_errors
        return rows

    def _download(self, url: str) -> bytes:
        """Download a gzip object with bounded retries and compressed size."""
        for attempt in range(self.max_retries + 1):
            try:
                response = self._request(url, stream=True, timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt == self.max_retries:
                    raise UpstreamAPIError(f"OpenAQ archive request failed: {exc}") from exc
                self._sleep(self.retry_backoff * (2**attempt))
                continue

            if response.status_code == 200:
                return self._read_limited(response.iter_content(chunk_size=64 * 1024))
            if response.status_code not in self.RETRYABLE_STATUS_CODES or attempt == self.max_retries:
                raise UpstreamAPIError(f"OpenAQ archive HTTP {response.status_code}: {response.text}")
            self._sleep(self.retry_backoff * (2**attempt))

        raise AssertionError("unreachable")

    def _read_limited(self, chunks: Iterator[bytes]) -> bytes:
        content = bytearray()
        for chunk in chunks:
            if not chunk:
                continue
            content.extend(chunk)
            if len(content) > self.max_download_bytes:
                raise UpstreamAPIError("OpenAQ archive download exceeds configured size limit")
        return bytes(content)

    def _filtered_rows(
        self, payload: bytes, *, sensor_id: Optional[int], parameter: Optional[str]
    ) -> Iterator[dict[str, str]]:
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(payload)) as compressed:
                decompressed = self._read_decompressed_limited(compressed)
        except (OSError, EOFError) as exc:
            raise UpstreamAPIError("OpenAQ archive returned an invalid gzip payload") from exc

        try:
            reader = csv.DictReader(io.TextIOWrapper(io.BytesIO(decompressed), encoding="utf-8-sig"))
            for row in reader:
                if sensor_id is not None and row.get("sensor_id", row.get("sensors_id")) != str(sensor_id):
                    continue
                if parameter is not None and row.get("parameter") != parameter:
                    continue
                yield row
        except (csv.Error, UnicodeDecodeError) as exc:
            raise UpstreamAPIError("OpenAQ archive returned an invalid CSV payload") from exc

    def _read_decompressed_limited(self, compressed: gzip.GzipFile) -> bytes:
        content = bytearray()
        while True:
            chunk = compressed.read(64 * 1024)
            if not chunk:
                return bytes(content)
            content.extend(chunk)
            if len(content) > self.max_decompressed_bytes:
                raise UpstreamAPIError("OpenAQ archive decompressed data exceeds configured size limit")

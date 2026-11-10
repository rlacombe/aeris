"""
Google Maps Air Quality API client.
"""

import logging
import warnings
from dataclasses import dataclass
from typing import Any, Optional

import requests

from ..exceptions import UpstreamAPIError

# Suppress Google API version warnings (Python 3.10 deprecation)
warnings.filterwarnings("ignore", category=FutureWarning, module="google.api_core")

logger = logging.getLogger(__name__)


@dataclass
class GoogleAirQualityClient:
    """
    Client for Google Maps Air Quality API.
    """

    api_key: str
    base_url: str = "https://airquality.googleapis.com/v1"

    def history_lookup(
        self,
        lat: float,
        lon: float,
        *,
        date_time_iso: Optional[str] = None,
        start_iso: Optional[str] = None,
        end_iso: Optional[str] = None,
        page_token: Optional[str] = None,
        page_size: int = 72,
        extra_computations: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Look up historical air quality data for a location.

        Args:
            lat, lon: Latitude and longitude
            date_time_iso: Specific datetime to lookup
            start_iso, end_iso: Time range to lookup
            page_token: Pagination token
            page_size: Number of results per page
            extra_computations: Additional computations to request

        Returns:
            API response data

        Raises:
            UpstreamAPIError: If API request fails
        """
        url = f"{self.base_url}/history:lookup?key={self.api_key}"
        payload: dict[str, Any] = {
            "location": {"latitude": lat, "longitude": lon},
            "pageSize": int(page_size),
            "universalAqi": False,
        }

        if extra_computations:
            payload["extraComputations"] = extra_computations
        if page_token:
            payload["pageToken"] = page_token
        if date_time_iso:
            payload["dateTime"] = date_time_iso
        elif start_iso and end_iso:
            payload["period"] = {"startTime": start_iso, "endTime": end_iso}
        else:
            raise ValueError("Either date_time_iso or (start_iso & end_iso) must be provided")

        r = requests.post(url, json=payload, timeout=30)

        # Parse error responses
        try:
            data = r.json()
        except (ValueError, requests.exceptions.JSONDecodeError):
            data = {}

        if "error" in data:
            msg = data["error"].get("message", "(no message)")
            raise UpstreamAPIError(f"Google Air Quality error: {msg}")

        if r.status_code != 200:
            raise UpstreamAPIError(f"Google Air Quality API HTTP {r.status_code}: {r.text}")

        # Warn if schema is unexpected
        if not any(
            k in data for k in ("hoursInfo", "hours", "hourlyReports", "indexes", "pollutants")
        ):
            logger.debug("Google AQ raw keys: %s", list(data.keys()))

        return data

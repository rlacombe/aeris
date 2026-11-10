"""
Open-Meteo API client.
"""

import logging
from typing import Any

import requests

from ..exceptions import UpstreamAPIError

logger = logging.getLogger(__name__)


class OpenMeteoClient:
    """Simple Open-Meteo API client for hourly variables."""

    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def get_hourly(self, lat: float, lon: float, start_iso: str, end_iso: str) -> dict[str, Any]:
        """
        Fetch hourly meteorological data from Open-Meteo.

        Args:
            lat: Latitude
            lon: Longitude
            start_iso: Start datetime in ISO format
            end_iso: End datetime in ISO format

        Returns:
            Dictionary with hourly weather data

        Raises:
            UpstreamAPIError: If API request fails
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": [
                "temperature_2m",
                "relative_humidity_2m",
                "windspeed_10m",
                "winddirection_10m",
                "precipitation",
            ],
            "start": start_iso,
            "end": end_iso,
            "timezone": "UTC",
        }
        r = requests.get(self.BASE_URL, params=params, timeout=20)
        if r.status_code != 200:
            raise UpstreamAPIError(f"Open-Meteo HTTP {r.status_code}: {r.text}")
        return r.json()

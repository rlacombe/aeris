"""
PurpleAir API client.
"""

import logging
import math
from typing import Any, Optional

import requests

from ..exceptions import UpstreamAPIError
from ..utils import haversine

logger = logging.getLogger(__name__)


class PurpleAirClient:
    """
    Minimal PurpleAir API v1 client for nearest sensor and hourly history.
    API key must be supplied via X-API-Key header.
    Notes: Endpoints may evolve; errors are surfaced as UpstreamAPIError.
    """

    BASE_URL = "https://api.purpleair.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        """Get HTTP headers with API key."""
        return {"X-API-Key": self.api_key}

    def nearest_sensor(
        self, lat: float, lon: float, radius_m: int = 25000
    ) -> Optional[dict[str, Any]]:
        """
        Find the nearest PurpleAir sensor to given coordinates.

        Args:
            lat: Latitude
            lon: Longitude
            radius_m: Search radius in meters (default 25km)

        Returns:
            Dictionary with 'fields', 'row', and 'distance_m' keys, or None if no sensor found
        """
        url = f"{self.BASE_URL}/sensors"
        # Convert radius (m) to degree deltas for a local bounding box
        # 1 deg latitude ≈ 111,000 m; lon scaled by cos(latitude)
        dlat = float(radius_m) / 111_000.0
        dlon = float(radius_m) / (111_000.0 * max(0.1, math.cos(math.radians(lat))))
        params = {
            "fields": "latitude,longitude,altitude,pm2.5,pm2.5_10minute,pm2.5_60minute,last_seen",
            "location_type": 0,
            "nwlng": lon - dlon,
            "nwlat": lat + dlat,
            "selng": lon + dlon,
            "selat": lat - dlat,
        }
        r = requests.get(url, headers=self._headers(), params=params, timeout=20)
        if r.status_code != 200:
            raise UpstreamAPIError(f"PurpleAir HTTP {r.status_code}: {r.text}")
        data = r.json()
        sensors = data.get("data", [])
        fields = data.get("fields", [])
        if not sensors or not fields:
            return None
        # Build list with distance and return nearest within radius
        idx_lat = fields.index("latitude") if "latitude" in fields else None
        idx_lon = fields.index("longitude") if "longitude" in fields else None
        if idx_lat is None or idx_lon is None:
            return None
        rows = []
        for s in sensors:
            try:
                d = haversine(lat, lon, float(s[idx_lat]), float(s[idx_lon]))
                rows.append((d, s))
            except (ValueError, TypeError):
                continue
        rows.sort(key=lambda x: x[0])
        if not rows:
            return None
        d, best = rows[0]
        if radius_m and d > radius_m:
            return None
        return {"fields": fields, "row": best, "distance_m": d}

    def hourly_history(self, sensor_index: int, start_iso: str, end_iso: str) -> dict[str, Any]:
        """
        Fetch hourly historical data from a PurpleAir sensor.

        Args:
            sensor_index: PurpleAir sensor index
            start_iso: Start datetime in ISO format
            end_iso: End datetime in ISO format

        Returns:
            Dictionary with sensor history data

        Raises:
            UpstreamAPIError: If API request fails
        """
        url = f"{self.BASE_URL}/sensors/{sensor_index}/history"
        params = {
            "fields": "pm2.5,humidity,temperature,pressure",
            "start_timestamp": start_iso,
            "end_timestamp": end_iso,
            "average": 60,
        }
        r = requests.get(url, headers=self._headers(), params=params, timeout=30)
        if r.status_code != 200:
            raise UpstreamAPIError(f"PurpleAir history HTTP {r.status_code}: {r.text}")
        return r.json()

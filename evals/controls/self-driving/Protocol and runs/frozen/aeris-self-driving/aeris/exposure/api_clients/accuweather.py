"""AccuWeather air-quality index client.

The public API identifies whether an AccuWeather location supports its
``AirQuality`` product and returns forecast air-quality index/category data.
Those values are provider indices, not mass concentrations. The client keeps
that distinction explicit so callers cannot silently use an index as PM$_{2.5}$
or another pollutant concentration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from ..exceptions import UpstreamAPIError


@dataclass
class AccuWeatherAirQualityClient:
    """Retrieve AccuWeather air-quality index information for a coordinate."""

    api_key: str
    base_url: str = "https://dataservice.accuweather.com"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Accept-Encoding": "gzip,deflate"}

    def _get(self, path: str, *, params: dict[str, Any]) -> Any:
        response = requests.get(
            f"{self.base_url}{path}",
            headers=self._headers(),
            params={**params, "format": "json"},
            timeout=30,
        )
        if response.status_code != 200:
            raise UpstreamAPIError(
                f"AccuWeather HTTP {response.status_code}: {response.text}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise UpstreamAPIError("AccuWeather returned invalid JSON") from exc

    def location_for_coordinate(self, latitude: float, longitude: float) -> dict[str, Any]:
        """Resolve a coordinate to an AccuWeather location and product set."""
        payload = self._get(
            "/locations/v1/geoposition/search",
            params={"q": f"{latitude},{longitude}", "details": "true"},
        )
        if not isinstance(payload, dict) or not payload.get("Key"):
            raise UpstreamAPIError("AccuWeather returned no location key for the coordinate")
        return payload

    def daily_air_quality(self, latitude: float, longitude: float) -> dict[str, Any]:
        """Return one-day air-quality index data and source metadata.

        AccuWeather exposes the index in the daily forecast's ``AirAndPollen``
        collection. No unit conversion is applied.
        """
        location = self.location_for_coordinate(latitude, longitude)
        datasets = set(location.get("DataSets") or [])
        if "AirQuality" not in datasets and "PremiumAirQuality" not in datasets:
            raise UpstreamAPIError(
                "AccuWeather does not advertise AirQuality for this location or subscription"
            )

        forecast = self._get(
            f"/forecasts/v1/daily/1day/{location['Key']}", params={"details": "true"}
        )
        daily = (forecast.get("DailyForecasts") or [{}])[0]
        entries = daily.get("AirAndPollen") or []
        air_quality = next(
            (entry for entry in entries if str(entry.get("Name", "")).lower() == "air quality"),
            None,
        )
        if air_quality is None:
            raise UpstreamAPIError("AccuWeather returned no air-quality index for this location")

        return {
            "source": "AccuWeather Air Quality API",
            "source_type": "air_quality_index",
            "latitude": latitude,
            "longitude": longitude,
            "location_key": location["Key"],
            "location_name": location.get("LocalizedName") or location.get("EnglishName"),
            "available_products": sorted(datasets),
            "forecast_date": daily.get("Date"),
            "index_name": air_quality.get("Name"),
            "index_value": air_quality.get("Value"),
            "category": air_quality.get("Category"),
            "category_value": air_quality.get("CategoryValue"),
            "dominant_pollutant": air_quality.get("Type"),
            "warning": (
                "AccuWeather reports a provider air-quality index. It is not a pollutant "
                "concentration and cannot be used as a concentration exposure variable."
            ),
        }

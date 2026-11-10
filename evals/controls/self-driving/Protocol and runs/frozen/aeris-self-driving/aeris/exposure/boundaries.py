"""Administrative-boundary resolution for area-level exposure assessment."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from shapely.geometry import Point, shape
from shapely.geometry.base import BaseGeometry

from .exceptions import InputValidationError, UpstreamAPIError

_GEObOUNDARIES_API = "https://www.geoboundaries.org/api/current/gbOpen"
_NAME_FIELDS = (
    "shapeName",
    "name",
    "NAME_0",
    "NAME_1",
    "NAME_2",
    "NAME_3",
    "NAME_4",
    "NAME_5",
    "name_en",
)


@dataclass(frozen=True)
class AdministrativeBoundary:
    """One administrative or researcher-supplied polygon with provenance."""

    name: str
    geometry: BaseGeometry
    source: str
    metadata: dict[str, Any]

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        """Return the boundary bounding box as min longitude, latitude, longitude, latitude."""
        return tuple(float(value) for value in self.geometry.bounds)

    def contains(self, latitude: float, longitude: float) -> bool:
        """Return whether a monitor coordinate is within or on the boundary."""
        return self.geometry.covers(Point(float(longitude), float(latitude)))

    def provenance(self) -> dict[str, Any]:
        """Return serializable boundary provenance for an exposure manifest."""
        return {"name": self.name, "source": self.source, **self.metadata}


def boundary_from_geojson(path: str | Path, feature_name: str | None = None) -> AdministrativeBoundary:
    """Load one boundary from a local GeoJSON geometry, feature, or collection.

    A feature collection with multiple geometries requires ``feature_name`` to
    avoid silently taking a union of administrative units.
    """
    geojson_path = Path(path).expanduser()
    if not geojson_path.is_file():
        raise InputValidationError(f"Boundary GeoJSON file not found: {geojson_path}")
    try:
        data = json.loads(geojson_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputValidationError(f"Could not read boundary GeoJSON: {exc}") from exc

    geometry, properties, selected_name = _select_geojson_geometry(data, feature_name)
    return AdministrativeBoundary(
        name=selected_name,
        geometry=geometry,
        source="researcher_supplied_geojson",
        metadata={"path": str(geojson_path.resolve()), "properties": properties},
    )


def boundary_names_from_geojson(path: str | Path) -> list[str]:
    """Return stable, unique feature names from a boundary collection."""
    geojson_path = Path(path).expanduser()
    if not geojson_path.is_file():
        raise InputValidationError(f"Boundary GeoJSON file not found: {geojson_path}")
    try:
        data = json.loads(geojson_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputValidationError(f"Could not read boundary GeoJSON: {exc}") from exc
    if data.get("type") != "FeatureCollection":
        raise InputValidationError("Batch boundary estimation requires a FeatureCollection.")
    names = [_feature_name(feature.get("properties") or {}) for feature in data.get("features") or []]
    if not names:
        raise InputValidationError("Boundary GeoJSON FeatureCollection is empty.")
    if any(name == "selected administrative boundary" for name in names):
        raise InputValidationError("Every boundary feature needs a stable name property.")
    normalized = [_normalize_name(name) for name in names]
    if len(set(normalized)) != len(normalized):
        raise InputValidationError("Boundary feature names must be unique.")
    return sorted(names, key=lambda value: _normalize_name(value))


def boundary_from_geoboundaries(
    iso3: str, adm_level: int, boundary_name: str | None = None
) -> AdministrativeBoundary:
    """Fetch an open administrative boundary from geoBoundaries.

    geoBoundaries provides a public metadata API and GeoJSON download URL. For
    ADM1--ADM5, callers must supply a unit name so the selected geography is
    never inferred from a centroid or silently unioned.
    """
    iso3 = iso3.upper()
    if len(iso3) != 3 or not iso3.isalpha():
        raise InputValidationError("iso3 must be an ISO 3166-1 alpha-3 country code.")
    if adm_level not in range(0, 6):
        raise InputValidationError("adm_level must be between 0 and 5.")
    if adm_level > 0 and not boundary_name:
        raise InputValidationError("boundary_name is required for ADM1 through ADM5.")

    metadata_url = f"{_GEObOUNDARIES_API}/{iso3}/ADM{adm_level}/"
    try:
        metadata_response = requests.get(metadata_url, timeout=30)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        geojson_url = metadata.get("gjDownloadURL")
        if not geojson_url:
            raise UpstreamAPIError("geoBoundaries response did not include gjDownloadURL.")
        geojson_response = requests.get(geojson_url, timeout=60)
        geojson_response.raise_for_status()
        data = geojson_response.json()
    except requests.RequestException as exc:
        raise UpstreamAPIError(f"geoBoundaries request failed: {exc}") from exc
    except ValueError as exc:
        raise UpstreamAPIError(f"geoBoundaries returned invalid JSON: {exc}") from exc

    geometry, properties, selected_name = _select_geojson_geometry(data, boundary_name)
    return AdministrativeBoundary(
        name=selected_name,
        geometry=geometry,
        source="geoBoundaries_gbOpen",
        metadata={
            "boundary_id": metadata.get("boundaryID"),
            "boundary_iso": metadata.get("boundaryISO", iso3),
            "boundary_type": metadata.get("boundaryType", f"ADM{adm_level}"),
            "boundary_year_represented": metadata.get("boundaryYearRepresented"),
            "boundary_source": metadata.get("boundarySource"),
            "license": metadata.get("boundaryLicense"),
            "metadata_url": metadata_url,
            "geometry_url": geojson_url,
            "selected_properties": properties,
        },
    )


def _select_geojson_geometry(
    data: dict[str, Any], feature_name: str | None
) -> tuple[BaseGeometry, dict[str, Any], str]:
    """Select and validate a single geometry from a GeoJSON object."""
    obj_type = data.get("type")
    if obj_type in {"Polygon", "MultiPolygon"}:
        geometry = shape(data)
        return _validated_geometry(geometry), {}, feature_name or "custom boundary"
    if obj_type == "Feature":
        geometry = shape(data.get("geometry"))
        properties = data.get("properties") or {}
        return _validated_geometry(geometry), properties, feature_name or _feature_name(properties)
    if obj_type != "FeatureCollection":
        raise InputValidationError("Boundary GeoJSON must be a geometry, Feature, or FeatureCollection.")

    features = data.get("features") or []
    if not features:
        raise InputValidationError("Boundary GeoJSON FeatureCollection is empty.")
    if feature_name:
        candidates = [
            feature
            for feature in features
            if _matches_name(feature.get("properties") or {}, feature_name)
        ]
        if not candidates:
            raise InputValidationError(f"No boundary feature matches '{feature_name}'.")
        if len(candidates) > 1:
            raise InputValidationError(f"Boundary name '{feature_name}' is ambiguous in this GeoJSON.")
        feature = candidates[0]
    elif len(features) == 1:
        feature = features[0]
    else:
        raise InputValidationError("Boundary GeoJSON has multiple features; provide boundary_name.")

    properties = feature.get("properties") or {}
    geometry = shape(feature.get("geometry"))
    return _validated_geometry(geometry), properties, _feature_name(properties)


def _validated_geometry(geometry: BaseGeometry) -> BaseGeometry:
    if geometry.is_empty or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        raise InputValidationError("Boundary must be a non-empty Polygon or MultiPolygon.")
    if not geometry.is_valid:
        raise InputValidationError("Boundary geometry is invalid; repair it before use.")
    return geometry


def _matches_name(properties: dict[str, Any], requested: str) -> bool:
    wanted = _normalize_name(requested)
    return any(_normalize_name(str(value)) == wanted for value in properties.values() if value is not None)


def _feature_name(properties: dict[str, Any]) -> str:
    for field in _NAME_FIELDS:
        value = properties.get(field)
        if value:
            return str(value)
    return "selected administrative boundary"


def _normalize_name(value: str) -> str:
    return " ".join(
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").casefold().split()
    )

"""
Overpass API client for road distance calculations.
"""

import logging
import math
from typing import Any, Optional

import requests

from ..utils import haversine

logger = logging.getLogger(__name__)


class OverpassClient:
    """Overpass API client to get distance to nearest highways/arterials."""

    BASE_URL = "https://overpass-api.de/api/interpreter"

    def dist_to_roads(self, lat: float, lon: float, radius_m: int = 10000) -> dict[str, float]:
        """
        Calculate distance to nearest highway and arterial road.

        Uses Overpass API to get full road geometries, then computes minimum
        distance from point to road line segments.

        Args:
            lat: Latitude
            lon: Longitude
            radius_m: Search radius in meters (default 10km)

        Returns:
            Dictionary with 'dist_hwy' and 'dist_art' keys (in meters), or None if not found
        """
        # Query highways and arterials separately with full geometry
        hwy_regex = "motorway|trunk|motorway_link|trunk_link"
        art_regex = "primary|secondary|primary_link|secondary_link"

        # Get highway distances
        dist_hwy = self._query_and_compute_distance(lat, lon, radius_m, hwy_regex, "highway")

        # Get arterial distances
        dist_art = self._query_and_compute_distance(lat, lon, radius_m, art_regex, "arterial")

        return {
            "dist_hwy": dist_hwy,
            "dist_art": dist_art,
        }

    def _query_and_compute_distance(
        self, lat: float, lon: float, radius_m: int, regex: str, road_type: str
    ) -> Optional[float]:
        """Query Overpass for roads matching regex and compute minimum distance."""
        # Cap radius to avoid timeouts
        search_radius = min(radius_m, 5000)

        q = f"""
        [out:json][timeout:25];
        (
          way(around:{search_radius},{lat},{lon})["highway"~"{regex}"];
        );
        out geom;
        """

        # Try with one retry on timeout
        for attempt in range(2):
            try:
                logger.debug("Querying Overpass for %s roads (attempt %d)", road_type, attempt + 1)

                r = requests.post(
                    self.BASE_URL,
                    data={"data": q},
                    timeout=30,
                    headers={"User-Agent": "AERIS Exposure/1.0"},
                )

                if r.status_code == 200:
                    data = r.json()
                    if data and "elements" in data:
                        dist = self._compute_min_distance_to_ways(lat, lon, data)
                        if dist is not None:
                            logger.debug("Found %s distance: %.1f m", road_type, dist)
                            return dist
                    logger.debug("No %s roads found within %d m", road_type, search_radius)
                    return None

                elif r.status_code == 504:
                    logger.debug("Overpass timeout (504) for %s roads", road_type)
                    if attempt < 1:
                        continue
                    break
                else:
                    logger.debug("Overpass HTTP %s for %s roads", r.status_code, road_type)
                    break

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                logger.debug(
                    "Overpass connection error for %s roads: %s", road_type, type(e).__name__
                )
                if attempt < 1:
                    continue
                break
            except (requests.RequestException, ValueError, KeyError) as e:
                logger.debug("Overpass error for %s roads: %s", road_type, type(e).__name__)
                break

        # Try with smaller radius if initial query failed
        if search_radius >= 2000:
            logger.debug("Retrying %s roads with smaller radius (2km)", road_type)
            return self._query_and_compute_distance(lat, lon, 2000, regex, road_type)

        logger.warning("Overpass API failed for %s roads after all retries", road_type)
        return None

    def _compute_min_distance_to_ways(
        self, lat: float, lon: float, data: dict[str, Any]
    ) -> Optional[float]:
        """
        Compute minimum distance from point to any road way.

        Uses Shapely if available for accurate geometry, otherwise falls back
        to point-to-segment distance calculation.
        """
        # Try to use Shapely for accurate geometry calculations
        try:
            from shapely.geometry import LineString, Point

            pt = Point(lon, lat)  # Shapely uses (x=lon, y=lat)
            min_dist = None

            for el in data.get("elements", []):
                if el.get("type") != "way":
                    continue

                # Get geometry nodes
                geometry = el.get("geometry", [])
                if len(geometry) < 2:
                    continue

                # Convert to LineString (lon, lat order for Shapely)
                coords = [(nd["lon"], nd["lat"]) for nd in geometry]
                line = LineString(coords)

                # Find nearest point on line
                nearest_on_line = line.interpolate(line.project(pt))

                # Compute haversine distance (Shapely distances are in degrees)
                d = haversine(lat, lon, nearest_on_line.y, nearest_on_line.x)

                if min_dist is None or d < min_dist:
                    min_dist = d

            return min_dist if min_dist is not None else None

        except ImportError:
            # Fallback: compute distance to each line segment manually
            min_dist = None

            for el in data.get("elements", []):
                if el.get("type") != "way":
                    continue

                geometry = el.get("geometry", [])
                if len(geometry) < 2:
                    continue

                # Check distance to each segment
                for i in range(len(geometry) - 1):
                    p1 = geometry[i]
                    p2 = geometry[i + 1]

                    # Distance to segment (approximate - point to closest point on segment)
                    seg_dist = self._point_to_segment_distance(
                        lat, lon, p1["lat"], p1["lon"], p2["lat"], p2["lon"]
                    )

                    if min_dist is None or seg_dist < min_dist:
                        min_dist = seg_dist

            return min_dist if min_dist is not None else None

    def _point_to_segment_distance(
        self,
        pt_lat: float,
        pt_lon: float,
        seg_lat1: float,
        seg_lon1: float,
        seg_lat2: float,
        seg_lon2: float,
    ) -> float:
        """
        Compute distance from point to line segment using haversine.

        Finds the closest point on the segment, then computes haversine distance.
        """
        # Convert to radians for calculations
        pt_lat_r, pt_lon_r = math.radians(pt_lat), math.radians(pt_lon)
        seg_lat1_r, seg_lon1_r = math.radians(seg_lat1), math.radians(seg_lon1)
        seg_lat2_r, seg_lon2_r = math.radians(seg_lat2), math.radians(seg_lon2)

        # Vector from segment start to end
        dx = seg_lon2_r - seg_lon1_r
        dy = seg_lat2_r - seg_lat1_r

        # Vector from segment start to point
        px = pt_lon_r - seg_lon1_r
        py = pt_lat_r - seg_lat1_r

        # Project point onto segment line
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq < 1e-10:  # Degenerate segment
            return haversine(pt_lat, pt_lon, seg_lat1, seg_lon1)

        t = max(0, min(1, (px * dx + py * dy) / seg_len_sq))

        # Closest point on segment
        closest_lat_r = seg_lat1_r + t * dy
        closest_lon_r = seg_lon1_r + t * dx

        # Convert back to degrees and compute haversine distance
        closest_lat = math.degrees(closest_lat_r)
        closest_lon = math.degrees(closest_lon_r)

        return haversine(pt_lat, pt_lon, closest_lat, closest_lon)

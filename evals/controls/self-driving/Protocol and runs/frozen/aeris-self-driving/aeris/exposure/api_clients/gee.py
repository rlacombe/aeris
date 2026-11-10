"""
Google Earth Engine client for LULC variables.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Import ee.EEException for targeted exception handling; fall back to Exception
# when earthengine-api is not installed so that except clauses remain valid.
try:
    import ee as _ee  # type: ignore

    _EEException = _ee.EEException
except Exception:  # pragma: no cover - optional dependency
    _EEException = Exception


class GEEClient:
    """
    Google Earth Engine client for LULC variables per collaborator specifications:

    - WA (waterbody), OS (open space), ISF (impervious): GLC_FCS30D (30m)
      Binary 0/1: Waterbody=210, Open space={200,201,202}, Impervious=190
    - TC (tree canopy): ESA CCI Plant Functional Types (PFT), returns percent
    - EL (elevation): Ensemble Digital Terrain Model (bare-earth), returns meters

    Requires earthengine-api and local authentication (run `earthengine authenticate`).
    """

    def __init__(self) -> None:
        # Lazy import to avoid hard dependency if unused
        try:
            import ee  # type: ignore

            self.ee = ee
        except Exception as e:
            raise RuntimeError(
                "earthengine-api not available; install with `pip install earthengine-api`"
            ) from e

        # Initialize EE (will use stored credentials if available). Support explicit project.
        try:
            project = os.getenv("AERIS_EXPOSURE_GEE_PROJECT")
            if project:
                self.ee.Initialize(project=project)
            else:
                self.ee.Initialize()
        except Exception as e:
            raise RuntimeError(
                "Google Earth Engine not initialized. Run `earthengine authenticate` and set a project via "
                "`earthengine set_project <PROJECT_ID>` or set env AERIS_EXPOSURE_GEE_PROJECT."
            ) from e

        # Dataset configuration per collaborator specifications
        # Using GEE datasets that best match OpenLandMap GLC_FCS30D, ESA CCI PFT, and Ensemble DTM
        self.cfg = {
            # GLC_FCS30D equivalent: Use ESA WorldCover (10m) or Dynamic World for better classification
            # ESA WorldCover classes: 10=tree, 20=shrub, 30=grassland, 40=cropland, 50=built,
            #                         60=bare, 70=snow, 80=water, 90=wetland, 95=moss
            "glc_dataset": os.getenv(
                "AERIS_EXPOSURE_GEE_GLC_DATASET", "ESA_WorldCover"
            ),  # ESA_WorldCover or DynamicWorld
            "glc_image": os.getenv(
                "AERIS_EXPOSURE_GEE_GLC_IMAGE", "ESA/WorldCover/v100"
            ),  # ESA WorldCover 2020
            "glc_band": os.getenv("AERIS_EXPOSURE_GEE_GLC_BAND", "Map"),
            # Tree canopy: ESA CCI PFT not in GEE, use Hansen/UMD global forest change (best proxy)
            "tc_image": os.getenv(
                "AERIS_EXPOSURE_GEE_TC_IMAGE", "UMD/hansen/global_forest_change_2024_v1_12"
            ),
            "tc_band": os.getenv(
                "AERIS_EXPOSURE_GEE_TC_BAND", "treecover2000"
            ),  # Percent tree cover (0-100)
            # Alternative: MODIS VCF "MODIS/061/MOD44B" band "Percent_Tree_Cover"
            # Ensemble DTM: Not in GEE, use Copernicus DEM GLO-30 as proxy (bare-earth, 30m)
            "dtm_image": os.getenv("AERIS_EXPOSURE_GEE_DTM_IMAGE", "COPERNICUS/DEM/GLO30"),
            "dtm_band": os.getenv("AERIS_EXPOSURE_GEE_DTM_BAND", "DEM"),
            # Sampling
            "buffer_m": int(
                os.getenv("AERIS_EXPOSURE_GEE_BUFFER_M", "0")
            ),  # Point sample for exact match
            "scale_m": int(os.getenv("AERIS_EXPOSURE_GEE_SCALE_M", "30")),
        }

    def _mean_band(self, image_id: str, band: str, geom, scale: int) -> Optional[float]:
        try:
            img = self.ee.Image(image_id).select(band).unmask(0)
            val = (
                img.reduceRegion(
                    reducer=self.ee.Reducer.mean(), geometry=geom, scale=scale, maxPixels=1_000_000
                )
                .get(band)
                .getInfo()
            )
            return float(val) if val is not None else None
        except (_EEException, RuntimeError):
            return None

    def _fraction_threshold(
        self, image_id: str, band: str, thresh: float, geom, scale: int
    ) -> Optional[float]:
        try:
            img = self.ee.Image(image_id).select(band).unmask(0)
            mask = img.gte(thresh)
            # Compute mean of boolean mask (fraction of pixels >= threshold) * 100
            val = (
                mask.reduceRegion(
                    reducer=self.ee.Reducer.mean(), geometry=geom, scale=scale, maxPixels=1_000_000
                )
                .get(band)
                .getInfo()
            )
            return (float(val) * 100.0) if val is not None else None
        except (_EEException, RuntimeError):
            return None

    def get_variables(self, lat: float, lon: float) -> dict[str, Optional[float]]:
        """
        Get LULC variables from GEE per collaborator specifications.

        Returns:
            Dict with keys: WA, OS, ISF (binary 0/1), TC (percent 0-100), EL (meters)
        """
        ee = self.ee
        point = ee.Geometry.Point([lon, lat])
        scale = int(self.cfg["scale_m"])

        # EL: Ensemble Digital Terrain Model (bare-earth) - Copernicus DEM GLO30
        el = self._mean_band(self.cfg["dtm_image"], self.cfg["dtm_band"], point, scale)
        if el is None:
            # Fallback to SRTM if Copernicus unavailable
            el = self._mean_band("USGS/SRTMGL1_003", "elevation", point, scale)
        el_val = float(el) if el is not None else None

        # GLC_FCS30D equivalent: Get land cover class at point and map to GLC_FCS30D classes
        # Using ESA WorldCover (10m) which has better classification than Copernicus
        glc_class = None
        try:
            # ESA WorldCover has clear classes we can map to GLC_FCS30D:
            # ESA WorldCover: 10=tree, 20=shrub, 30=grassland, 40=cropland, 50=built,
            #                60=bare/sparse, 70=snow, 80=water, 90=wetland, 95=moss
            # GLC_FCS30D: 210=waterbody, 190=impervious, 200/201/202=open space

            # ESA WorldCover is an ImageCollection - get the 2020 image
            # Collection structure: ESA/WorldCover/v100 with year property
            try:
                lc_coll = ee.ImageCollection(self.cfg["glc_image"])
                # Filter for 2020 (most common year) or get first available
                lc_img = lc_coll.filterDate("2020-01-01", "2020-12-31").first()
                if lc_img is None:
                    lc_img = lc_coll.first()
            except (_EEException, RuntimeError):
                # If collection access fails, try as Image
                lc_img = ee.Image(self.cfg["glc_image"])

            lc_class = (
                lc_img.select(self.cfg["glc_band"])
                .reduceRegion(reducer=ee.Reducer.mode(), geometry=point, scale=scale, maxPixels=10)
                .get(self.cfg["glc_band"])
                .getInfo()
            )

            if lc_class is not None:
                lc_class = int(lc_class)
                logger.debug("ESA WorldCover class at (%.4f, %.4f): %d", lat, lon, lc_class)

                # Map ESA WorldCover classes to GLC_FCS30D classes per collaborator spec:
                # GLC_FCS30D: 210=waterbody, 190=impervious, 200/201/202=open space
                # ESA WorldCover: 10=tree, 20=shrub, 30=grassland, 40=cropland, 50=built,
                #                60=bare/sparse, 70=snow, 80=water, 90=wetland, 95=moss

                if lc_class == 80:  # Water (80) -> GLC_FCS30D 210
                    glc_class = 210
                elif lc_class == 50:  # Built-up (50) -> GLC_FCS30D 190 (impervious)
                    glc_class = 190
                elif lc_class in {
                    10,
                    20,
                    30,
                    40,
                    60,
                    70,
                    90,
                    95,
                }:  # Open space types -> GLC_FCS30D 200
                    # Tree (10), shrub (20), grassland (30), cropland (40), bare (60), snow (70),
                    # wetland (90), moss (95) -> open space (includes tree-covered parks and green spaces)
                    glc_class = 200

                logger.debug(
                    "Mapped ESA WorldCover class %d -> GLC_FCS30D class %s", lc_class, glc_class
                )
                if glc_class is not None:
                    wa_bin = 1 if glc_class == 210 else 0
                    os_bin = 1 if glc_class in {200, 201, 202} else 0
                    isf_bin = 1 if glc_class == 190 else 0
                    logger.debug(
                        "Resulting binary flags: WA=%d, OS=%d, ISF=%d", wa_bin, os_bin, isf_bin
                    )
                else:
                    # Unmapped classes result in all zeros
                    logger.debug(
                        "ESA WorldCover class %d (unmapped) -> GLC_FCS30D None -> WA=0, OS=0, ISF=0",
                        lc_class,
                    )
            else:
                logger.warning("ESA WorldCover returned None at (%.4f, %.4f)", lat, lon)
        except (_EEException, RuntimeError) as e:
            logger.debug("ESA WorldCover fetch failed at (%.4f, %.4f): %s", lat, lon, e)
            # Fallback to Copernicus if ESA WorldCover fails
            try:
                cop_coll = ee.ImageCollection("COPERNICUS/Landcover/100m/Proba-V-C3/Global")
                cop_img = cop_coll.first()
                cop_class = (
                    cop_img.select("discrete_classification")
                    .reduceRegion(
                        reducer=ee.Reducer.mode(), geometry=point, scale=100, maxPixels=10
                    )
                    .get("discrete_classification")
                    .getInfo()
                )

                if cop_class is not None:
                    cop_class = int(cop_class)
                    logger.debug("Copernicus fallback: class %d", cop_class)
                    # Map Copernicus to GLC_FCS30D
                    # Copernicus classes: 0=water, 20=built-up, 30=bare/sparse, 40=grassland,
                    #                     50=shrubland, 60=tree, 70=cropland, 80=snow, 90=shrub, 100=herbaceous
                    if cop_class == 0:  # Water -> GLC_FCS30D 210
                        glc_class = 210
                    elif cop_class == 20:  # Built-up -> GLC_FCS30D 190 (impervious)
                        glc_class = 190
                    elif cop_class in {
                        30,
                        40,
                        50,
                        60,
                        70,
                        80,
                        90,
                        100,
                    }:  # Open space types -> GLC_FCS30D 200
                        # Bare (30), grassland (40), shrubland (50), tree (60), cropland (70),
                        # snow (80), shrub (90), herbaceous (100) -> open space (includes tree-covered parks and green spaces)
                        glc_class = 200
            except (_EEException, RuntimeError) as e2:
                logger.debug("Copernicus fallback also failed: %s", e2)

        # WA: Binary from GLC_FCS30D class 210 (waterbody)
        wa_val = 1.0 if (glc_class == 210) else 0.0

        # ISF: Binary from GLC_FCS30D class 190 (impervious)
        isf_val = 1.0 if (glc_class == 190) else 0.0

        # OS: Binary from GLC_FCS30D classes 200, 201, 202 (open space)
        os_val = 1.0 if (glc_class in {200, 201, 202}) else 0.0

        # TC: Tree canopy percent
        # Note: ESA CCI PFT is NOT in GEE, so use Hansen/UMD or MODIS VCF as proxy
        tc_val = None
        try:
            # Try Hansen/UMD tree cover (primary choice)
            # This gives percent tree cover (0-100) for year 2000 baseline
            hansen_img = ee.Image(self.cfg["tc_image"]).select(self.cfg["tc_band"])
            tc_val = (
                hansen_img.reduceRegion(
                    reducer=ee.Reducer.mean(), geometry=point, scale=scale, maxPixels=1000
                )
                .get(self.cfg["tc_band"])
                .getInfo()
            )

            if tc_val is not None:
                tc_val = float(tc_val)
                logger.debug("Hansen/UMD tree cover at (%.4f, %.4f): %.2f%%", lat, lon, tc_val)
            else:
                logger.warning("Hansen/UMD tree cover returned None at (%.4f, %.4f)", lat, lon)
        except (_EEException, RuntimeError) as e:
            logger.debug("Hansen/UMD tree cover fetch failed: %s", e)

        # Fallback to MODIS VCF if Hansen unavailable
        if tc_val is None:
            try:
                tc_val = self._mean_band("MODIS/061/MOD44B", "Percent_Tree_Cover", point, scale)
                if tc_val is not None:
                    logger.debug(
                        "Using MODIS VCF fallback for TC at (%.4f, %.4f): %.2f%%", lat, lon, tc_val
                    )
            except (_EEException, RuntimeError) as e:
                logger.debug("MODIS VCF fallback also failed: %s", e)
                tc_val = None

        return {
            "WA": wa_val,
            "OS": os_val,
            "ISF": isf_val,
            "TC": float(tc_val) if tc_val is not None else None,
            "EL": el_val,
        }

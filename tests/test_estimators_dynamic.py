"""
Tests for dynamic mode estimators (Google Maps and XGBoost).
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from aeris.exposure.config import Config
from aeris.exposure.estimators.dynamic import (
    ExposureEstimatorGoogleMapsDynamic,
    ExposureEstimatorXGBDynamic,
)
from aeris.exposure.exceptions import ConfigurationError

# Common patch stack for XGB tests: mock all external clients including GEE
_XGB_PATCHES = [
    "aeris.exposure.estimators.dynamic.OverpassClient",
    "aeris.exposure.estimators.dynamic.OpenMeteoClient",
    "aeris.exposure.estimators.dynamic.PurpleAirClient",
]


def _patch_xgb_init(func):
    """Decorator that patches all XGB external dependencies including GEE."""
    for target in reversed(_XGB_PATCHES):
        func = patch(target)(func)
    func = patch("aeris.exposure.api_clients.GEEClient")(func)
    return func


class TestGmapsInit:
    """Test ExposureEstimatorGoogleMapsDynamic initialization."""

    @patch("aeris.exposure.estimators.dynamic.GoogleAirQualityClient")
    def test_valid_init(self, mock_client):
        est = ExposureEstimatorGoogleMapsDynamic(
            input_csv="data.csv",
            config=Config(google_maps_api_key="test_key"),
        )
        assert est.config.google_maps_api_key == "test_key"

    def test_missing_api_key_raises(self):
        with pytest.raises(ConfigurationError, match="Missing Google Maps"):
            ExposureEstimatorGoogleMapsDynamic(
                input_csv="data.csv",
                config=Config(),
            )

    @patch("aeris.exposure.estimators.dynamic.GoogleAirQualityClient")
    def test_api_key_override(self, mock_client):
        est = ExposureEstimatorGoogleMapsDynamic(
            input_csv="data.csv",
            gmaps_api_key="override_key",
            config=Config(),
        )
        assert est.config.google_maps_api_key == "override_key"


class TestMapUnit:
    """Test the _map_unit static method."""

    def test_micrograms(self):
        assert ExposureEstimatorGoogleMapsDynamic._map_unit("MICROGRAMS_PER_CUBIC_METER") == "µg/m³"

    def test_ppb(self):
        assert ExposureEstimatorGoogleMapsDynamic._map_unit("PARTS_PER_BILLION") == "ppb"

    def test_ppm(self):
        assert ExposureEstimatorGoogleMapsDynamic._map_unit("PARTS_PER_MILLION") == "ppm"

    def test_unknown(self):
        assert ExposureEstimatorGoogleMapsDynamic._map_unit("UNKNOWN_UNIT") is None

    def test_none(self):
        assert ExposureEstimatorGoogleMapsDynamic._map_unit(None) is None


class TestXgbInit:
    """Test ExposureEstimatorXGBDynamic initialization."""

    def test_missing_purpleair_key_raises(self):
        with pytest.raises(ConfigurationError, match="Missing PurpleAir"):
            ExposureEstimatorXGBDynamic(
                input_csv="data.csv",
                config=Config(),
            )

    @_patch_xgb_init
    def test_missing_model_raises(self, mock_gee, mock_pa, mock_met, mock_osm, tmp_path):
        """Test that missing model raises when no default model exists."""
        # Run from tmp_path so no xgb_model.json is found in cwd
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            with pytest.raises(ConfigurationError, match="Missing XGBoost model"):
                ExposureEstimatorXGBDynamic(
                    input_csv="data.csv",
                    purpleair_api_key="pa_key",
                    config=Config(),
                )
        finally:
            os.chdir(original_cwd)

    @_patch_xgb_init
    def test_valid_init_with_json_model(self, mock_gee, mock_pa, mock_met, mock_osm, tmp_path):
        model_file = tmp_path / "model.json"
        model_file.write_text("{}")

        est = ExposureEstimatorXGBDynamic(
            input_csv="data.csv",
            purpleair_api_key="pa_key",
            model_path=str(model_file),
            config=Config(),
        )
        assert est.config.purpleair_api_key == "pa_key"
        assert est.config.xgb_model_path == str(model_file)


class TestXgbLoadModel:
    """Test model loading logic."""

    @_patch_xgb_init
    def test_load_json_model(self, mock_gee, mock_pa, mock_met, mock_osm, tmp_path):
        model_file = tmp_path / "model.json"
        model_file.write_text("{}")

        est = ExposureEstimatorXGBDynamic(
            input_csv="data.csv",
            purpleair_api_key="pa_key",
            model_path=str(model_file),
            config=Config(),
        )

        mock_booster = MagicMock()
        # Patch at the module level where it's imported inside _load_model
        with patch.dict("sys.modules", {"xgboost": MagicMock()}):
            import sys

            mock_xgb = sys.modules["xgboost"]
            mock_xgb.Booster.return_value = mock_booster
            est._load_model()
            mock_booster.load_model.assert_called_once_with(str(model_file))
            assert est._model is mock_booster

    @_patch_xgb_init
    def test_load_json_model_with_features(self, mock_gee, mock_pa, mock_met, mock_osm, tmp_path):
        model_file = tmp_path / "model.json"
        model_file.write_text("{}")

        features_file = tmp_path / "features.txt"
        features_file.write_text("re_pm25\ntemperature\nhumidity\n")

        est = ExposureEstimatorXGBDynamic(
            input_csv="data.csv",
            purpleair_api_key="pa_key",
            model_path=str(model_file),
            config=Config(),
        )
        assert est.config.xgb_feature_names_path == str(features_file)

    @_patch_xgb_init
    def test_packaged_model_loads_and_predicts(self, mock_gee, mock_pa, mock_met, mock_osm):
        """The distributed Booster must remain usable by the dynamic pathway."""
        model_path = Path(__file__).resolve().parents[1] / "xgb_model.json"
        assert model_path.exists(), "The packaged XGBoost model is missing."

        est = ExposureEstimatorXGBDynamic(
            input_csv="data.csv",
            purpleair_api_key="pa_key",
            model_path=str(model_path),
            config=Config(),
        )
        model = est._load_model()

        import xgboost as xgb

        prediction = model.predict(xgb.DMatrix(np.zeros((1, model.num_features()))))
        assert prediction.shape == (1,)
        assert np.isfinite(prediction[0])

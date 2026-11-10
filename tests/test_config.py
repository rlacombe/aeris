"""
Tests for configuration management.
"""

from pathlib import Path
from unittest.mock import patch

from aeris.exposure.config import ALLOWED_POLLUTANTS, Config, get_package_root


class TestAllowedPollutants:
    """Test the ALLOWED_POLLUTANTS constant."""

    def test_contains_expected_pollutants(self):
        expected = {"pm25", "pm10", "so2", "no2", "co", "o3"}
        assert set(ALLOWED_POLLUTANTS) == expected

    def test_has_six_entries(self):
        assert len(ALLOWED_POLLUTANTS) == 6


class TestConfig:
    """Test Config dataclass."""

    def test_defaults(self):
        cfg = Config()
        assert cfg.openaq_api_key is None
        assert cfg.google_maps_api_key is None
        assert cfg.purpleair_api_key is None
        assert cfg.accuweather_api_key is None
        assert cfg.xgb_model_path is None
        assert cfg.xgb_feature_names_path is None
        assert cfg.openaq_calls_per_minute == 50
        assert cfg.openaq_calls_per_hour == 2000
        assert cfg.search_radius == 25000
        assert cfg.station_limit == 1000
        assert cfg.generate_plots is True
        assert cfg.dpi == 300

    def test_custom_values(self):
        cfg = Config(
            openaq_api_key="test_key",
            openaq_calls_per_minute=10,
            search_radius=50000,
        )
        assert cfg.openaq_api_key == "test_key"
        assert cfg.openaq_calls_per_minute == 10
        assert cfg.search_radius == 50000

    @patch.dict(
        "os.environ",
        {
            "OPENAQ_API_KEY": "oaq_key",
            "GOOGLE_MAPS_AIR_QUALITY_API_KEY": "gm_key",
            "PURPLEAIR_API_KEY": "pa_key",
            "ACCUWEATHER_API_KEY": "aw_key",
            "AERIS_EXPOSURE_XGB_MODEL_PATH": "/tmp/model.json",
            "AERIS_EXPOSURE_XGB_FEATURES": "/tmp/features.txt",
        },
    )
    def test_from_env_with_vars(self):
        cfg = Config.from_env()
        assert cfg.openaq_api_key == "oaq_key"
        assert cfg.google_maps_api_key == "gm_key"
        assert cfg.purpleair_api_key == "pa_key"
        assert cfg.accuweather_api_key == "aw_key"
        assert cfg.xgb_model_path == "/tmp/model.json"
        assert cfg.xgb_feature_names_path == "/tmp/features.txt"

    @patch("aeris.exposure.config.Path.exists", return_value=False)
    @patch.dict("os.environ", {}, clear=True)
    def test_from_env_without_vars(self, _path_exists):
        cfg = Config.from_env()
        assert cfg.openaq_api_key is None
        assert cfg.google_maps_api_key is None
        assert cfg.purpleair_api_key is None
        assert cfg.accuweather_api_key is None

    def test_from_env_preserves_defaults(self):
        cfg = Config.from_env()
        assert cfg.openaq_calls_per_minute == 50
        assert cfg.openaq_calls_per_hour == 2000
        assert cfg.search_radius == 25000

    def test_from_env_uses_explicit_environment_file(self, tmp_path, monkeypatch):
        env_file = tmp_path / "aeris.env"
        env_file.write_text("OPENAQ_API_KEY=file-key\n")
        monkeypatch.delenv("OPENAQ_API_KEY", raising=False)
        monkeypatch.setenv("AERIS_ENV_FILE", str(env_file))

        cfg = Config.from_env()

        assert cfg.openaq_api_key == "file-key"


class TestGetPackageRoot:
    """Test get_package_root utility."""

    def test_returns_path(self):
        result = get_package_root()
        assert isinstance(result, Path)

    def test_contains_aeris_exposure_subdir(self):
        root = get_package_root()
        assert (root / "exposure").is_dir()

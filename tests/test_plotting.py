"""
Tests for plotting modules (no-crash, basic output validation).
"""

import matplotlib

matplotlib.use("Agg")  # non-interactive backend

import pandas as pd

from aeris.exposure.plotting.dynamic_plotter import DynamicPlotter
from aeris.exposure.plotting.static_plotter import StaticPlotter


class TestStaticPlotter:
    """Test StaticPlotter methods."""

    def test_init(self):
        plotter = StaticPlotter("pm25")
        assert plotter.pollutant == "pm25"

    def test_distance_qc_empty_df(self):
        """plot_distance_qc with empty DataFrame should return unchanged."""
        plotter = StaticPlotter("pm25")
        df = pd.DataFrame()
        result = plotter.plot_distance_qc(df)
        assert result.empty

    def test_distance_qc_none_input(self):
        """plot_distance_qc with None should return None."""
        plotter = StaticPlotter("pm25")
        result = plotter.plot_distance_qc(None)
        assert result is None

    def test_distance_qc_missing_column(self):
        """plot_distance_qc without distance_m column should return unchanged."""
        plotter = StaticPlotter("pm25")
        df = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})
        result = plotter.plot_distance_qc(df)
        assert len(result) == 1

    def test_distance_qc_with_threshold(self, tmp_path, monkeypatch):
        """plot_distance_qc filters subjects beyond threshold."""
        monkeypatch.chdir(tmp_path)
        plotter = StaticPlotter("pm25")
        df = pd.DataFrame(
            {
                "subject_id": ["S001", "S002", "S003"],
                "distance_m": [1000, 15000, 50000],  # 1km, 15km, 50km
                "mean": [10.0, 12.0, 8.0],
            }
        )
        result = plotter.plot_distance_qc(df, distance_threshold_km=20.0)
        # S003 (50km) should be excluded
        assert len(result) == 2
        assert "S003" not in result["subject_id"].values

    def test_distance_qc_no_threshold_keeps_all(self, tmp_path, monkeypatch):
        """plot_distance_qc without threshold keeps all subjects."""
        monkeypatch.chdir(tmp_path)
        plotter = StaticPlotter("pm25")
        df = pd.DataFrame(
            {
                "subject_id": ["S001", "S002"],
                "distance_m": [1000, 50000],
                "mean": [10.0, 8.0],
            }
        )
        result = plotter.plot_distance_qc(df, distance_threshold_km=None)
        assert len(result) == 2

    def test_distance_qc_ignores_missing_station_distances(self, tmp_path):
        """QC plots retain rows for subjects without a qualifying station."""
        plotter = StaticPlotter("pm10", output_dir=tmp_path)
        df = pd.DataFrame(
            {
                "subject_id": ["with-data", "without-data"],
                "distance_m": [1200.0, float("nan")],
                "mean": [20.0, float("nan")],
            }
        )

        result = plotter.plot_distance_qc(df)

        assert len(result) == 2
        assert (tmp_path / "distance_plot_pm10.png").exists()

    def test_distance_qc_primary_distance_column(self, tmp_path, monkeypatch):
        """plot_distance_qc accepts primary_distance_m from IDW mode."""
        monkeypatch.chdir(tmp_path)
        plotter = StaticPlotter("pm25")
        df = pd.DataFrame(
            {
                "subject_id": ["S001", "S002"],
                "primary_distance_m": [1000, 50000],
                "mean": [10.0, 8.0],
            }
        )
        result = plotter.plot_distance_qc(df, distance_threshold_km=20.0)
        assert len(result) == 1
        assert "S001" in result["subject_id"].values

    def test_distance_qc_output_dir(self, tmp_path):
        """Plots are written under output_dir when configured."""
        out = tmp_path / "plots"
        plotter = StaticPlotter("pm25", output_dir=out)
        df = pd.DataFrame(
            {
                "subject_id": ["S001"],
                "distance_m": [1000],
                "mean": [10.0],
            }
        )
        plotter.plot_distance_qc(df)
        assert (out / "distance_plot_pm25.png").exists()

    def test_heatmaps_empty_data(self):
        """plot_daily_heatmaps with empty dict should not crash."""
        plotter = StaticPlotter("pm25")
        plotter.plot_daily_heatmaps({})  # should just return/log warning


class TestDynamicPlotter:
    """Test DynamicPlotter methods."""

    def test_init(self):
        plotter = DynamicPlotter()
        assert plotter is not None

    def test_route_map_too_few_points(self):
        """plot_route_map with <2 valid points should not crash."""
        plotter = DynamicPlotter()
        df = pd.DataFrame(
            {
                "latitude": [40.7],
                "longitude": [-74.0],
                "pm25": [10.0],
                "timestamp_utc": ["2024-01-01T00:00:00Z"],
            }
        )
        # Should return early without error
        plotter.plot_route_map(df, "pm25", "µg/m³")

    def test_route_map_all_nan(self):
        """plot_route_map with all-NaN values should not crash."""
        plotter = DynamicPlotter()
        df = pd.DataFrame(
            {
                "latitude": [40.7, 40.8],
                "longitude": [-74.0, -73.9],
                "pm25": [None, None],
                "timestamp_utc": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
            }
        )
        plotter.plot_route_map(df, "pm25", "µg/m³")

    def test_boxplots_empty_data(self):
        """plot_boxplots with empty DataFrame should not crash."""
        plotter = DynamicPlotter()
        df = pd.DataFrame()
        plotter.plot_boxplots(df, {})

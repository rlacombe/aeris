"""
Tests for the CLI argument parsing and dispatch logic.
"""

from unittest.mock import patch

import pandas as pd
import pytest

from aeris.exposure.cli import main


def _write_static_csv(path):
    """Write a minimal valid static CSV to the given path."""
    df = pd.DataFrame(
        {
            "subject_id": ["S001"],
            "zip": ["10001"],
            "start_date": ["2024-01-01"],
            "end_date": ["2024-01-31"],
        }
    )
    df.to_csv(path, index=False)


def _write_dynamic_csv(path):
    """Write a minimal valid dynamic CSV to the given path."""
    df = pd.DataFrame(
        {
            "subject_id": ["S001"] * 3,
            "timestamp": [
                "2024-01-01T00:00:00Z",
                "2024-01-01T01:00:00Z",
                "2024-01-01T02:00:00Z",
            ],
            "latitude": [40.7128] * 3,
            "longitude": [-74.0060] * 3,
        }
    )
    df.to_csv(path, index=False)


class TestArgumentParsing:
    """Test that CLI arguments are parsed correctly."""

    def test_missing_input_file_exits(self):
        """CLI exits when no input file is given."""
        with patch("sys.argv", ["aeris.exposure"]), pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2  # argparse error

    def test_nonexistent_input_file_exits(self):
        """CLI exits with code 1 when input file doesn't exist."""
        with (
            patch("sys.argv", ["aeris.exposure", "/nonexistent/file.csv", "--pollutant", "pm25"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 1

    def test_invalid_pollutant_exits(self):
        """CLI exits when an invalid pollutant is provided."""
        with (
            patch("sys.argv", ["aeris.exposure", "data.csv", "--pollutant", "invalid"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 2

    def test_invalid_dynamic_backend_exits(self):
        """CLI exits when an invalid backend is provided."""
        with (
            patch("sys.argv", ["aeris.exposure", "data.csv", "--dynamic_backend", "invalid"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            main()
        assert exc_info.value.code == 2


class TestModeDispatch:
    """Test that the CLI dispatches to the correct estimator."""

    def test_static_mode_creates_openaq_estimator(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch("sys.argv", ["aeris.exposure", csv_path, "--pollutant", "pm25"]),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            main()

            MockCls.assert_called_once_with(
                input_csv=csv_path,
                pollutant="pm25",
                api_key=None,
                distance_threshold_km=None,
                country="us",
                min_completeness=None,
                cache=None,
                n_stations=1,
                outlier_detection=False,
            )
            MockCls.return_value.run.assert_called_once_with(
                output_csv=None, raw_output=False, skip_confirm=False
            )

    def test_dynamic_gmaps_creates_gmaps_estimator(self, tmp_path):
        csv_path = str(tmp_path / "dynamic.csv")
        _write_dynamic_csv(csv_path)

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch("sys.argv", ["aeris.exposure", csv_path, "--dynamic_backend", "gmaps"]),
            patch("aeris.exposure.cli.detect_mode", return_value="dynamic"),
            patch("aeris.exposure.cli.ExposureEstimatorGoogleMapsDynamic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            main()

            MockCls.assert_called_once_with(
                input_csv=csv_path,
                gmaps_api_key=None,
                cache=None,
            )

    def test_dynamic_xgb_creates_xgb_estimator(self, tmp_path):
        csv_path = str(tmp_path / "dynamic.csv")
        _write_dynamic_csv(csv_path)

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch("sys.argv", ["aeris.exposure", csv_path, "--dynamic_backend", "xgb"]),
            patch("aeris.exposure.cli.detect_mode", return_value="dynamic"),
            patch("aeris.exposure.cli.ExposureEstimatorXGBDynamic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            main()

            MockCls.assert_called_once_with(
                input_csv=csv_path,
                purpleair_api_key=None,
                openaq_api_key=None,
                model_path=None,
                cache=None,
            )

    def test_static_mode_requires_pollutant(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)

        with patch("sys.argv", ["aeris.exposure", csv_path]), pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1


class TestErrorHandling:
    """Test that CLI handles errors with correct exit codes."""

    def test_configuration_error_exits_1(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)

        from aeris.exposure.exceptions import ConfigurationError

        with (
            patch("sys.argv", ["aeris.exposure", csv_path, "--pollutant", "pm25"]),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
            pytest.raises(SystemExit) as exc_info,
        ):
            MockCls.side_effect = ConfigurationError("missing key")
            main()
        assert exc_info.value.code == 1

    def test_keyboard_interrupt_exits_0(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)

        with (
            patch("sys.argv", ["aeris.exposure", csv_path, "--pollutant", "pm25"]),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
            pytest.raises(SystemExit) as exc_info,
        ):
            MockCls.side_effect = KeyboardInterrupt
            main()
        assert exc_info.value.code == 0

    def test_empty_result_exits_1(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)

        with (
            patch("sys.argv", ["aeris.exposure", csv_path, "--pollutant", "pm25"]),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
            pytest.raises(SystemExit) as exc_info,
        ):
            MockCls.return_value.run.return_value = pd.DataFrame()
            main()
        assert exc_info.value.code == 1


class TestYesFlag:
    """Test --yes / -y flag passes skip_confirm to run()."""

    def test_yes_flag_is_parsed(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch("sys.argv", ["aeris.exposure", csv_path, "--pollutant", "pm25", "--yes"]),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            main()

            MockCls.return_value.run.assert_called_once_with(
                output_csv=None, raw_output=False, skip_confirm=True
            )

    def test_short_yes_flag(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch("sys.argv", ["aeris.exposure", csv_path, "--pollutant", "pm25", "-y"]),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            main()

            MockCls.return_value.run.assert_called_once_with(
                output_csv=None, raw_output=False, skip_confirm=True
            )


class TestThresholdFlag:
    """Test --threshold flag is parsed and passed to estimator."""

    def test_threshold_flag_is_parsed(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch(
                "sys.argv",
                ["aeris.exposure", csv_path, "--pollutant", "pm25", "--threshold", "35.0"],
            ),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            main()

            # Verify threshold attribute was set on the estimator instance
            assert MockCls.return_value.threshold == 35.0


class TestDailyFlag:
    """Test --daily flag calls get_daily_data() and writes CSV."""

    def test_daily_flag_calls_get_daily_data(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)
        daily_csv = str(tmp_path / "daily.csv")

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})
        mock_daily = pd.DataFrame(
            {"subject_id": ["S001"], "date": ["2024-01-01"], "parameter": ["pm25"], "mean": [10.0]}
        )

        with (
            patch(
                "sys.argv",
                ["aeris.exposure", csv_path, "--pollutant", "pm25", "--daily", daily_csv],
            ),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            MockCls.return_value.get_daily_data.return_value = mock_daily
            main()

            MockCls.return_value.get_daily_data.assert_called_once()
            # Verify the daily CSV was written
            written_df = pd.read_csv(daily_csv)
            assert len(written_df) == 1

    def test_country_flag_is_parsed(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch(
                "sys.argv",
                ["aeris.exposure", csv_path, "--pollutant", "pm25", "--country", "gb"],
            ),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            main()

            MockCls.assert_called_once_with(
                input_csv=csv_path,
                pollutant="pm25",
                api_key=None,
                distance_threshold_km=None,
                country="gb",
                min_completeness=None,
                cache=None,
                n_stations=1,
                outlier_detection=False,
            )

    def test_min_completeness_flag(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch(
                "sys.argv",
                ["aeris.exposure", csv_path, "--pollutant", "pm25", "--min_completeness", "75.0"],
            ),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            main()

            MockCls.assert_called_once_with(
                input_csv=csv_path,
                pollutant="pm25",
                api_key=None,
                distance_threshold_km=None,
                country="us",
                min_completeness=75.0,
                cache=None,
                n_stations=1,
                outlier_detection=False,
            )

    def test_pollutant_all_flag(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch(
                "sys.argv",
                ["aeris.exposure", csv_path, "--pollutant", "all"],
            ),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            main()

            MockCls.assert_called_once_with(
                input_csv=csv_path,
                pollutant="all",
                api_key=None,
                distance_threshold_km=None,
                country="us",
                min_completeness=None,
                cache=None,
                n_stations=1,
                outlier_detection=False,
            )

    def test_cache_flag(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch(
                "sys.argv",
                ["aeris.exposure", csv_path, "--pollutant", "pm25", "--cache"],
            ),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            main()

            # Cache should be a ResponseCache instance (not None)
            call_kwargs = MockCls.call_args[1]
            assert call_kwargs["cache"] is not None

    def test_n_stations_flag(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch(
                "sys.argv",
                ["aeris.exposure", csv_path, "--pollutant", "pm25", "--n_stations", "3"],
            ),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            main()

            call_kwargs = MockCls.call_args[1]
            assert call_kwargs["n_stations"] == 3

    def test_output_dir_flag(self, tmp_path):
        """--output_dir is passed to the estimator and resolves relative CSV paths."""
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)
        out_dir = tmp_path / "results_idw5"

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch(
                "sys.argv",
                [
                    "aeris",
                    csv_path,
                    "--pollutant",
                    "pm25",
                    "--output_dir",
                    str(out_dir),
                    "--output_csv",
                    "month_results.csv",
                    "--daily",
                    "month_daily.csv",
                    "-y",
                ],
            ),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
        ):
            mock_est = MockCls.return_value
            mock_est.run.return_value = mock_result
            mock_est.get_daily_data.return_value = pd.DataFrame(
                {"subject_id": ["S001"], "date": ["2024-01-01"], "mean": [10.0]}
            )
            main()

            call_kwargs = MockCls.call_args[1]
            assert call_kwargs["output_dir"] == out_dir
            run_kwargs = mock_est.run.call_args[1]
            assert run_kwargs["output_csv"] == str(out_dir / "month_results.csv")
            assert out_dir.exists()
            assert (out_dir / "month_daily.csv").exists()

    def test_outlier_detection_flag(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch(
                "sys.argv",
                ["aeris.exposure", csv_path, "--pollutant", "pm25", "--outlier_detection"],
            ),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            main()

            call_kwargs = MockCls.call_args[1]
            assert call_kwargs["outlier_detection"] is True

    def test_format_geojson_flag(self, tmp_path):
        csv_path = str(tmp_path / "dynamic.csv")
        _write_dynamic_csv(csv_path)

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch(
                "sys.argv",
                [
                    "aeris.exposure",
                    csv_path,
                    "--dynamic_backend",
                    "gmaps",
                    "--format",
                    "geojson",
                    "--output_csv",
                    str(tmp_path / "out.csv"),
                ],
            ),
            patch("aeris.exposure.cli.detect_mode", return_value="dynamic"),
            patch("aeris.exposure.cli.ExposureEstimatorGoogleMapsDynamic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            # Should not raise (geojson warning if no lat/lon columns)
            main()

    def test_long_format_flag(self, tmp_path):
        csv_path = str(tmp_path / "static.csv")
        _write_static_csv(csv_path)
        long_csv = str(tmp_path / "long.csv")

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})
        mock_raw = pd.DataFrame(
            {
                "subject_id": ["S001"],
                "timestamp_utc": ["2024-01-01T00:00:00Z"],
                "value": [10.0],
                "parameter": ["pm25"],
            }
        )

        with (
            patch(
                "sys.argv",
                ["aeris.exposure", csv_path, "--pollutant", "pm25", "--long_format", long_csv],
            ),
            patch("aeris.exposure.cli.ExposureEstimatorOpenAQStatic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            MockCls.return_value.get_raw_data.return_value = mock_raw
            main()

            MockCls.return_value.get_raw_data.assert_called_once()
            written = pd.read_csv(long_csv)
            assert len(written) == 1

    def test_daily_flag_warns_for_dynamic(self, tmp_path):
        csv_path = str(tmp_path / "dynamic.csv")
        _write_dynamic_csv(csv_path)

        mock_result = pd.DataFrame({"subject_id": ["S001"], "mean": [10.0]})

        with (
            patch(
                "sys.argv",
                ["aeris.exposure", csv_path, "--dynamic_backend", "gmaps", "--daily", "daily.csv"],
            ),
            patch("aeris.exposure.cli.detect_mode", return_value="dynamic"),
            patch("aeris.exposure.cli.ExposureEstimatorGoogleMapsDynamic") as MockCls,
        ):
            MockCls.return_value.run.return_value = mock_result
            # Should not raise, just warn
            main()
            # get_daily_data should NOT be called for dynamic mode
            assert (
                not hasattr(MockCls.return_value, "get_daily_data")
                or not MockCls.return_value.get_daily_data.called
            )

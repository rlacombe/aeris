"""
Tests for input validation functions.
"""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from aeris.exposure.exceptions import InputValidationError
from aeris.exposure.validators import detect_mode, validate_dynamic_input, validate_static_input


class TestDetectMode:
    """Test mode detection functionality."""

    def test_detect_static_mode_zip(self):
        """Test detection of static mode with ZIP column."""
        data = {
            "subject_id": ["S001", "S002"],
            "zip": ["10001", "10002"],
            "start_date": ["2024-01-01", "2024-01-01"],
            "end_date": ["2024-01-31", "2024-01-31"],
        }
        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            result = detect_mode(f.name)
            assert result == "static"

        Path(f.name).unlink()

    def test_detect_static_mode_address(self):
        """Test detection of static mode with address column."""
        data = {
            "subject_id": ["S001"],
            "address": ["123 Main St"],
            "start_date": ["2024-01-01"],
            "end_date": ["2024-01-31"],
        }
        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            result = detect_mode(f.name)
            assert result == "static"

        Path(f.name).unlink()

    def test_detect_static_mode_coordinates(self):
        """A dated static cohort may provide fixed coordinates directly."""
        data = {
            "subject_id": ["S001"],
            "latitude": [40.7128],
            "longitude": [-74.0060],
            "start_date": ["2024-01-01"],
            "end_date": ["2024-01-31"],
        }
        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            assert detect_mode(f.name) == "static"

        Path(f.name).unlink()

    def test_detect_dynamic_mode(self):
        """Test detection of dynamic mode."""
        data = {
            "subject_id": ["S001"] * 24,
            "timestamp": [f"2024-01-01T{i:02d}:00:00Z" for i in range(24)],
            "latitude": [40.7128] * 24,
            "longitude": [-74.0060] * 24,
        }
        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            result = detect_mode(f.name)
            assert result == "dynamic"

        Path(f.name).unlink()

    def test_detect_mode_invalid_schema(self):
        """Test detection fails with invalid schema."""
        data = {"invalid_col": ["test"]}
        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name, index=False)
            with pytest.raises(InputValidationError):
                detect_mode(f.name)

        Path(f.name).unlink()

    def test_detect_mode_file_not_found(self):
        """Test detection fails with non-existent file."""
        with pytest.raises(InputValidationError):
            detect_mode("nonexistent.csv")


class TestValidateStaticInput:
    """Test static input validation."""

    def test_valid_static_input_zip(self):
        """Test validation of valid static input with ZIP."""
        data = {
            "subject_id": ["S001", "S002"],
            "zip": ["10001", "10002"],
            "start_date": ["2024-01-01", "2024-01-01"],
            "end_date": ["2024-01-31", "2024-01-31"],
        }
        df = pd.DataFrame(data)
        result = validate_static_input(df)

        assert "start_dt" in result.columns
        assert "end_dt" in result.columns
        assert len(result) == 2

    def test_valid_static_input_address(self):
        """Test validation of valid static input with address."""
        data = {
            "subject_id": ["S001"],
            "address": ["123 Main St"],
            "start_date": ["2024-01-01"],
            "end_date": ["2024-01-31"],
        }
        df = pd.DataFrame(data)
        result = validate_static_input(df)

        assert len(result) == 1
        assert "start_dt" in result.columns

    def test_missing_required_columns(self):
        """Test validation fails with missing required columns."""
        data = {
            "subject_id": ["S001"],
            "start_date": ["2024-01-01"],
            # Missing end_date
        }
        df = pd.DataFrame(data)

        with pytest.raises(InputValidationError, match="Missing columns"):
            validate_static_input(df)

    def test_missing_location_columns(self):
        """Test validation fails when neither zip nor address is provided."""
        data = {
            "subject_id": ["S001"],
            "start_date": ["2024-01-01"],
            "end_date": ["2024-01-31"],
            # Missing both zip and address
        }
        df = pd.DataFrame(data)

        with pytest.raises(InputValidationError, match="requires either"):
            validate_static_input(df)

    def test_invalid_date_range(self):
        """Test validation fails when end_date is before start_date."""
        data = {
            "subject_id": ["S001"],
            "zip": ["10001"],
            "start_date": ["2024-01-31"],
            "end_date": ["2024-01-01"],  # End before start
        }
        df = pd.DataFrame(data)

        with pytest.raises(InputValidationError, match="end_date earlier than start_date"):
            validate_static_input(df)


class TestValidateDynamicInput:
    """Test dynamic input validation."""

    def test_valid_dynamic_input(self):
        """Test validation of valid dynamic input."""
        data = {
            "subject_id": ["S001"] * 24,
            "timestamp": [f"2024-01-01T{i:02d}:00:00Z" for i in range(24)],
            "latitude": [40.7128] * 24,
            "longitude": [-74.0060] * 24,
        }
        df = pd.DataFrame(data)
        result = validate_dynamic_input(df)

        assert len(result) == 24
        assert "dt" in result.columns
        assert "hour" in result.columns

    def test_missing_required_columns(self):
        """Test validation fails with missing required columns."""
        data = {
            "subject_id": ["S001"],
            "timestamp": ["2024-01-01T00:00:00Z"],
            # Missing latitude and longitude
        }
        df = pd.DataFrame(data)

        with pytest.raises(InputValidationError, match="requires columns"):
            validate_dynamic_input(df)

    def test_multiple_subjects_accepted(self):
        """Test validation accepts multiple subjects."""
        data = {
            "subject_id": ["S001", "S002"] * 12,
            "timestamp": [f"2024-01-01T{i:02d}:00:00Z" for i in range(24)],
            "latitude": [40.7128] * 24,
            "longitude": [-74.0060] * 24,
        }
        df = pd.DataFrame(data)
        result = validate_dynamic_input(df)
        assert set(result["subject_id"].unique()) == {"S001", "S002"}

    def test_invalid_coordinates(self):
        """Test validation fails with invalid coordinates."""
        data = {
            "subject_id": ["S001"] * 24,
            "timestamp": [f"2024-01-01T{i:02d}:00:00Z" for i in range(24)],
            "latitude": [91.0] * 24,  # Invalid latitude > 90
            "longitude": [-74.0060] * 24,
        }
        df = pd.DataFrame(data)

        with pytest.raises(InputValidationError, match="Latitude out of range"):
            validate_dynamic_input(df)

    def test_multi_day_accepted(self):
        """Test validation accepts more than 24 hours (multi-day)."""
        timestamps = [f"2024-01-01T{i:02d}:00:00Z" for i in range(24)]
        timestamps.append("2024-01-02T00:00:00Z")

        data = {
            "subject_id": ["S001"] * 25,
            "timestamp": timestamps,
            "latitude": [40.7128] * 25,
            "longitude": [-74.0060] * 25,
        }
        df = pd.DataFrame(data)
        result = validate_dynamic_input(df)
        assert len(result) == 25

    def test_per_subject_dedup(self):
        """Test hour deduplication works per-subject."""
        data = {
            "subject_id": ["S001", "S001", "S002"],
            "timestamp": [
                "2024-01-01T00:00:00Z",
                "2024-01-01T00:30:00Z",  # same hour as first for S001
                "2024-01-01T00:00:00Z",
            ],
            "latitude": [40.7128] * 3,
            "longitude": [-74.0060] * 3,
        }
        df = pd.DataFrame(data)
        result = validate_dynamic_input(df)
        # S001 should have 1 row (deduped), S002 should have 1 row
        assert len(result) == 2
        assert len(result[result["subject_id"] == "S001"]) == 1
        assert len(result[result["subject_id"] == "S002"]) == 1

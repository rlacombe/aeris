# Changelog

## Unreleased

- Treat scientifically equivalent public source substitutions as first-class
  autonomous analysis plans.
- Balance web-search results across general and repository routes, and require
  source-level discovery for every failed data role.
- Reject fitted reanalyses whose temporal sample or comparison groups cannot
  support the selected model.
- Preserve article-defined model logic and contrasts; keep agent-created bins,
  thresholds, and replacement models exploratory.
- Simplify self-driving reanalysis around one article-derived plan, open-ended
  execution, one skeptical review, and a compact final fidelity record.
- Remove mandatory competing-plan matrices, exhaustive unit and month ledgers,
  and generic sample-size thresholds from autonomous completion.
- Require terminal blocker reviews to preserve structured public-dataset search
  responses and evidence-backed dispositions for every candidate, across at
  least two discovery routes.

- Added a narrow scientific-invariant contract for autonomous reanalysis.
- Added evidence-backed, append-only execution-design amendments.
- Added a durable research notebook for restart-safe long-running work.
- Replaced checklist-only blocker claims with executable attempt evidence.
- Simplified the reanalysis profile around standing authority and skeptical review.
- Added full-article evidence maps before scientific invariants are locked.
- Added separate outcome, exposure, and analysis supports with candidate-plan comparison.
- Required feasible probe expansion, unit-level attempt ledgers, and covariate recovery evidence.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **OpenAQ fallback for XGBoost dynamic mode**: When no PurpleAir PM2.5 sensors are found within 5km of target coordinates, the system automatically queries OpenAQ for PM2.5 measurements within a 25km radius. This improves coverage in areas with limited PurpleAir sensor density.
- INFO-level logging to indicate PM2.5 data source (PurpleAir or OpenAQ) for each GPS point in XGB mode.
- **Code refactoring for improved maintainability**: Reorganized codebase into modular structure:
  - `aeris.exposure/estimators/` - Separated static and dynamic estimators
  - `aeris.exposure/api_clients/` - Individual service client modules
  - `aeris.exposure/plotting/` - Separated static and dynamic plotters
- **DataFrame input support**: `ExposureEstimatorOpenAQStatic` now accepts pandas DataFrames directly in addition to CSV file paths, enabling data loading from any source without intermediate file storage.
- **Coordinate-based location input**: Static mode now supports latitude/longitude coordinates as an alternative to ZIP codes or addresses, skipping geocoding for faster and more accurate processing.
- **Programmatic data access methods**: Added `get_raw_data()` and `get_daily_data()` methods to `ExposureEstimatorOpenAQStatic` for accessing raw hourly measurements and daily aggregates programmatically without parsing CSV files.
- **Auto-logging configuration**: Estimators now automatically configure logging if not already set up, ensuring informative messages are visible when running in Python scripts.

### Changed
- XGBoost dynamic mode now searches PurpleAir sensors within 5km radius (previously 3km) to match OpenAQ fallback threshold.
- Improved logging visibility: PM2.5 source information now appears at INFO level instead of DEBUG.
- **Code structure**: Large monolithic files split into focused modules for better organization and maintainability. Package directories now handle all imports directly.
- **Distance filtering**: Removed interactive prompt for distance filtering. Filtering now works automatically based on `distance_threshold_km` parameter if provided.
- **Logging improvements**: Workload estimates are now printed to console before user prompts, providing context for decision-making.

### Removed
- **PurpleAirStatic estimator**: Removed `ExposureEstimatorPurpleAirStatic` class (static mode now uses OpenAQ only)
- **Legacy compatibility files**: Removed `aeris.exposure/estimators.py`, `aeris.exposure/api_clients.py`, and `aeris.exposure/plotting.py` (no longer needed as package directories handle imports)

## [0.1.0] - 2025-11-04

### Added
- Initial release of AERIS Exposure
- Static mode using OpenAQ API for historical air quality data
- Dynamic mode with Google Maps Air Quality API for real-time GPS-based tracking
- Dynamic mode with XGBoost dispersion model for PM2.5 predictions
- Support for all six standard air pollutants (PM2.5, PM10, SO2, NO2, CO, O3)
- Comprehensive visualization tools (route plots, heatmaps, boxplots)
- Robust API client implementations with rate limiting and retry logic
- Support for multiple Overpass API endpoints for road distance calculations
- Google Earth Engine integration for Land Use/Land Cover variables
- Command-line interface with auto-detection of static vs dynamic modes
- Python API for programmatic use
- Example data files and documentation
- Comprehensive test suite

### Features
- Automatic geocoding of ZIP codes and addresses
- Distance-based quality control for sensor data
- Raw data export capabilities
- Error handling and graceful degradation
- Environment variable and .env file support
- Detailed logging and debug modes

# Getting Started

## Installation

```bash
pip install aeris
```

## API Keys

AERIS Exposure uses external air quality APIs. Set your keys as environment variables:

```bash
# Static mode (OpenAQ)
export OPENAQ_API_KEY="your-key"

# Dynamic mode (Google Maps Air Quality)
export GOOGLE_MAPS_AIR_QUALITY_API_KEY="your-key"

# Dynamic mode (XGBoost — PurpleAir for PM2.5 readings)
export PURPLEAIR_API_KEY="your-key"

# Optional: current/forecast AccuWeather air-quality index inspection
export ACCUWEATHER_API_KEY="your-key"
```

## Static Mode Example

Estimate PM2.5 exposure for subjects with ZIP codes:

```bash
aeris exposure data.csv --pollutant pm25 --output_csv results.csv
```

Input CSV format:

```csv
subject_id,zip,start_date,end_date
S001,10001,2024-01-01,2024-01-31
S002,90001,2024-01-01,2024-01-31
```

### Python API

```python
from aeris.exposure import ExposureEstimatorOpenAQStatic

estimator = ExposureEstimatorOpenAQStatic(
    input_csv="data.csv",
    pollutant="pm25",
)
result = estimator.run(skip_confirm=True)
```

## Dynamic Mode Example

Estimate exposure along GPS trajectories:

```bash
aeris exposure gps.csv --dynamic_backend gmaps --output_csv results.csv
```

Input CSV format:

```csv
subject_id,timestamp,latitude,longitude
S001,2024-01-01T08:00:00Z,40.7128,-74.0060
S001,2024-01-01T09:00:00Z,40.7138,-74.0070
```

## Advanced Options

```bash
# Multi-pollutant analysis
aeris exposure data.csv --pollutant all

# IDW multi-station averaging (3 nearest stations)
aeris exposure data.csv --pollutant pm25 --n_stations 3

# Outlier detection
aeris exposure data.csv --pollutant pm25 --outlier_detection

# GeoJSON output (dynamic mode)
aeris exposure gps.csv --dynamic_backend gmaps --format geojson --output_csv results.csv

# Response caching for resume-on-failure
aeris exposure data.csv --pollutant pm25 --cache

# International ZIP codes (France)
aeris exposure data.csv --pollutant pm25 --country fr
```

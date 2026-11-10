# CLI Reference

## Usage

```
aeris exposure INPUT_CSV [OPTIONS]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `INPUT_CSV` | Path to input CSV file |

## Options

### Output

| Flag | Description |
|------|-------------|
| `--output_csv PATH` | Summary CSV output path |
| `--raw` | Save raw measurement data as CSV files |
| `--daily DAILY_CSV` | Daily-aggregated output (static mode only) |
| `--long_format LONG_CSV` | Long-format tidy output (one row per measurement) |
| `--format {csv,geojson}` | Output format (default: csv; geojson requires geopandas) |

### Static Mode

| Flag | Description |
|------|-------------|
| `--pollutant {pm25,pm10,so2,no2,co,o3,all}` | Pollutant to analyze (required for static) |
| `--country CODE` | ISO country code for ZIP geocoding (default: us) |
| `--distance_threshold KM` | Auto-exclude subjects beyond this distance |
| `--n_stations N` | Number of stations for IDW averaging (default: 1) |
| `--min_completeness PCT` | Minimum data completeness % (0-100) |

### Dynamic Mode

| Flag | Description |
|------|-------------|
| `--dynamic_backend {gmaps,xgb}` | Backend engine (default: gmaps) |
| `--model_path PATH` | XGB model file path |

### Data Quality

| Flag | Description |
|------|-------------|
| `--threshold VALUE` | Concentration threshold for exceedance counting |
| `--outlier_detection` | Enable IQR-based outlier detection |

### API Keys

| Flag | Description |
|------|-------------|
| `--api_key KEY` | OpenAQ API key |
| `--gmaps_api_key KEY` | Google Maps Air Quality API key |
| `--purpleair_api_key KEY` | PurpleAir API key |

### Caching

| Flag | Description |
|------|-------------|
| `--cache` | Enable SQLite response caching |
| `--cache_path PATH` | Cache database file path |
| `--clear_cache` | Clear cache and exit |

### Other

| Flag | Description |
|------|-------------|
| `--yes`, `-y` | Skip interactive confirmation |
| `--debug` | Enable debug logging |
| `--version` | Show version |

# PMID 33484722: OECD COVID-19

This run reconstructs the paper's 36-country long-term PM2.5 analysis with
the official WHO COVID-19 global CSV, World Bank indicator APIs, and AERIS
country-boundary PM2.5. It does not use the paper's exposure values.

## Target analysis

The published target is Table 1: four multivariable linear regressions of log
country case and death rates on day 60 and day 80 after the first reported
case. This reconstruction substitutes an AERIS/OpenAQ 2017 PM2.5 summary.

The paper's original exposure was a World Bank **population-weighted** annual
PM2.5 estimate. AERIS computes an **unweighted mean of contributing
OpenAQ-monitor means within the country boundary**. The original Table 1 also
included a percentage-above-guideline PM2.5 variable. That term requires a
population surface, while AERIS produces a monitor-network mean.

The closest complete public-data model adjusts for age 65+, density, and GDP
per capita. World Bank physician and hospital-bed values leave too few complete
records for the fuller covariate specification. The completed model uses 11
countries with at least 65% annual AERIS network coverage. See `RESULT.md` for
the estimates and `reproduction_model_results.csv` for all fitted models.

## Public sources

- WHO outcomes: `https://srhdpeuwpubsa.blob.core.windows.net/whdh/COVID/WHO-COVID-19-global-data.csv`
- World Bank population: `SP.POP.TOTL`
- World Bank population aged 65+: `SP.POP.65UP.TO.ZS`
- World Bank physicians: `SH.MED.PHYS.ZS`
- World Bank hospital beds: `SH.MED.BEDS.ZS`
- World Bank surface area: `AG.SRF.TOTL.K2`
- World Bank GDP per capita: `NY.GDP.PCAP.CD`
- Exposure: OpenAQ v3 and OpenAQ historical S3 through AERIS
  `estimate_boundary_exposure`

`public-inputs/source_manifest.json` records fetch time and SHA-256 checksums.

## Run

```bash
python acquire_public_inputs.py
python run_aeris_tools.py
python fit_reproduction.py
```

For a resumable one-country retrieval:

```bash
AERIS_COUNTRIES=AUS python run_aeris_tools.py
```

The OpenAQ response cache is local-only and excluded from git. The script uses
the recorded ten-request-per-minute limit and reuses cached locations and
sensor-day responses.

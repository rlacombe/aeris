# Replication protocol

## Target

PMID 36197352 studies daily COVID-19 admissions among residents of Taubate,
Tremembe, and Pindamonhangaba from 1 April 2020 through 31 March 2021.
The published outcome is SIH/SUS admissions with ICD-10 B34.2. Its primary
analysis fits multipollutant negative-binomial models over lags 0 through 7.

The reported comparison targets are PM2.5 lag 2, RR 1.0216 per 5 ug/m3, and
NO2 lag 7, RR 1.0124 per 10 ug/m3.

## Reconstruction

1. `run_aeris_discovery.py` sends the three municipal locations and study
   window through the AERIS tool contract. It records the selected OpenAQ
   location, distance, coverage, and decision log.
2. `fetch_cetesb_daily.py` retrieves the complete daily historical series for
   CETESB station 58, Taubate. AERIS selected the correspondingly named local
   OpenAQ location 5231 for each municipal centroid. The file is resumable and
   paced at one request per second.
3. `fetch_sih_sus.py` downloads the twelve public SIH/SUS RD files. `ingest_sih_sus.py`
   reads `MUNIC_RES`, `DT_INTER`, and `DIAG_PRINC`, retaining the three
   municipal residence codes and B34.2 admissions.
4. `fetch_weather.py` retrieves daily temperature and relative humidity at the
   Taubate centroid from Open-Meteo.
5. `build_panel.py` creates the 365-day panel and the 0--7 day pollutant lags.
6. `fit_negative_binomial.py` fits each lag with PM2.5, NO2, O3, temperature,
   humidity, a linear day index, and weekday indicators. It reports the
   published PM2.5 and NO2 increments.

The completion record names the coverage and all departures from the original
analysis. No paper-provided pollution values enter this reconstruction.

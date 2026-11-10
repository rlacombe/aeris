# Result

Status: exposure reconstruction complete; outcome acquisition incomplete.

## AERIS exposure record

AERIS selected OpenAQ location 5231, Taubate, for all three municipal
centroids: 1.5 km from Taubate, 8.1 km from Tremembe, and 15.8 km from
Pindamonhangaba. OpenAQ and its S3 archive supplied 79 days. The public
CETESB historical form recovered the full study-window record from the
corresponding Taubate station (58):

- PM2.5: 362 of 365 days.
- NO2: 355 of 365 days.
- O3: 341 of 365 days.
- Temperature and relative humidity: 365 of 365 days from Open-Meteo.

`data/derived/cetesb_download.json` records the source request, coverage, and
response-stream SHA-256. `data/derived/aeris_discovery.json` and
`data/derived/aeris_tool_trace.json` record the AERIS calls and monitor choice.

## Public SIH/SUS outcome

The official SIH/SUS RD files `RDSP2004.dbc` and `RDSP2005.dbc` were retrieved
and decoded. Filtering `MUNIC_RES` to Taubate, Tremembe, and Pindamonhangaba,
`DIAG_PRINC` to B34.2, and `DT_INTER` to the paper's dates produced 28 daily
admissions through 31 May 2020. The schema and filter are verified in
`data/derived/sih_sus_ingestion.json`.

The official FTP server timed out on all June--August 2020 transfer attempts.
The canonical downloader retains the public URLs, bounded retries, and a file
manifest so the remaining ten monthly files can be acquired and the model run
without changing the protocol. The current 61-day outcome record cannot support
the paper's 365-day lagged negative-binomial analysis.

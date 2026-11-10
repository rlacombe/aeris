# Reanalysis decision log

Study: PMID 33227571, *Cluster of climatic and pollutant characteristics increases admissions for acute myocardial infarction*.

## Locked reconstruction target

- Outcome: daily SUS hospital admissions for acute myocardial infarction (AMI), intended ICD-10 I21, summed over the 39 municipalities in metropolitan São Paulo.
- Period: the supplied article says 2012--2015. The article abstract also reports cluster sizes totaling 1,092 days, which is inconsistent with four complete calendar years; no full-text methods or supplement were supplied to resolve this discrepancy.
- Environmental variables: PM2.5, PM10, NO2, temperature variation, rainfall, and relative humidity; daily environmental-condition clusters (three groups).
- Published principal comparison: admissions in the high-pollution/adverse-weather cluster versus the other clusters. The abstract reports 30.5 admissions/day (IQR 25.0--36.0) and a 9% increase, but does not supply a regression coefficient, CI, cluster algorithm settings, or an unambiguous model.

## Inputs and decisions

1. The author pollution values, exposure table, code, and fitted fields were not used.
2. Attempted the official DataSUS SIH-SUS `RDSP1201.dbc` release. Both HTTPS and HTTP connections to `ftp.datasus.gov.br` timed out. The current official DataSUS transfer portal was reachable, but its direct SIHSUS/RD query returned HTTP 500 with an empty body. No daily admissions microdata were obtained or inspected.
3. The transfer portal identifies `RD` as AIH Reduzida, a UF-level SIHSUS data file. It is the same outcome construct, not an outcome substitution.
4. Queried independent Open-Meteo historical air-quality data at central São Paulo. It explicitly rejects 2012 as out of range. Its 2013--2015 replies contain timestamps but zero non-null PM2.5, PM10, NO2, temperature, humidity, or precipitation values. Timestamp-only rows were excluded from `exposure_daily.csv`.
5. No analysis panel can be constructed: 0 outcome days and 0 usable exposure days. No cluster assignment, statistical test, or model was run.

## Coverage decision

The article’s stated 39 municipalities are treated as eligible units. The stated 2012--2015 interval contains 1,461 calendar days, but the exact analytic date range cannot be locked from the supplied materials. Inclusion is zero because neither requisite data stream supplied usable daily values. This is a coverage blocker, not a scientific substitution.

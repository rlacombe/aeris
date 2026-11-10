# Protocol

## Target

Yu et al. estimate short-term PM2.5 associations with cancer mortality across
Brazil. The target comparison is their 2015--2019 all-cancer estimate: odds
ratio 1.01 per 10 ug/m3 PM2.5.

## Reconstruction

- **Outcome:** daily national count of deaths in public SIM resident files,
  2015--2019, using the cancer ICD-10 code ranges stated in the article.
- **Exposure:** daily unweighted mean of public PM2.5 monitor means returned
  by AERIS inside the Brazil ADM0 boundary. AERIS retrieves OpenAQ v3 data and
  the public historical S3 archive through its normal tool contract. When that
  audit yields fewer than 180 complete days, the IEMA standardized public
  state-monitor archives provide the documented recovery record.
- **Weather:** daily unweighted mean temperature and relative humidity at
  retained monitor coordinates from Open-Meteo.
- **Model:** weighted conditional logistic likelihood, with each death date
  matched to dates in the same weekday and month. PM2.5, temperature, and
  humidity use three-day moving averages (lag 0--2). PM2.5 is scaled per
  10 ug/m3. National statutory holidays are included.

## Data sufficiency rule

The model requires 180 complete lagged days. The rule is fixed before fitting.
It prevents a sparse monitor series from producing a nominal national effect.

## Source substitution

The article used a population-weighted 0.25-degree PM2.5 machine-learning
surface and population-weighted ERA5 weather. This reconstruction uses a
public monitor network and monitor-location weather. `source_manifest.json`
records the source URLs and each executable step writes a retrieval manifest.

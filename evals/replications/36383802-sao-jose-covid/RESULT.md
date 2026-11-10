# Result

Status: completed bounded reconstruction using a public SIVEP-Gripe outcome
fallback.

## AERIS exposure record

AERIS assigned the Jacareí OpenAQ location, 14.6 km from the São José dos
Campos centroid. The OpenAQ v3 and historical S3 workflow recovered 106 PM10,
102 NO2, and 98 ozone daily values between 12 January and 23 April 2021. The
full paper window runs from 1 April 2020 through 30 April 2021.

## Outcome record and model

The paper uses SIH/SUS B34.2 admissions. The official monthly SIH/SUS transfer
did not deliver its RD files during this run. The completed model uses the
public SIVEP-Gripe severe-respiratory-hospitalization archive, filtered to São
José dos Campos residents admitted with COVID-19. It contains 7,110 admissions
over the 395-day study window.

The negative-binomial model includes ozone at lag 2, NO2 at lag 3, PM10 at lag
0, temperature, relative humidity, weekday, and linear calendar day. It fits
89 complete days and 2,112 admissions:

| Effect per 10 ug/m3 | Published | AERIS reconstruction |
| --- | ---: | ---: |
| Ozone, lag 2 | 1.061 (1.016-1.108) | 1.003 (0.981-1.026) |
| NO2, lag 3 | 1.125 (1.050-1.205) | 1.034 (0.876-1.220) |

The result is recorded in `outputs/effect_results_sivep_fallback.json`. It is
useful evidence that the AERIS workflow can form and fit a daily panel from
public inputs. The changed outcome definition and 89-day exposure record mean
it does not enter the strict effect-calibration metrics.

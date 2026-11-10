# Result

**Status:** AERIS S3 audit completed. The target PM2.5 reconstruction has no
municipal variation. A closest public measured-pollutant NO2 sensitivity model
was fitted.

The public Israeli Ministry of Health municipal outcome data and cited CBS
locality population and coordinates were recovered and converted into an AERIS
cohort. AERIS ran four annual PM2.5 estimates, each using the public OpenAQ S3
fallback within the archive's bounded automatic retrieval window.

The PM2.5 run recovered 314 daily values in 2016 (mean 15.016 ug/m3), 239 in
2017 (14.050 ug/m3), and 50 in 2019 (13.019 ug/m3) from SPARTAN - Weizmann
Institute (location `1285358`, sensor `6566251`). It recovered no 2018 record.
Each nonempty annual output contains 38 municipalities, one station assignment,
and one exposure value.

Joining the July 24, 2020 public outcome data to the AERIS study-period panel
retains 38 municipalities, but their PM2.5 standard deviation and range are
both zero. The pollutant is collinear with the intercept, so the public model
does not estimate a PM2.5 effect. The scoped output files
`aeris_pm25_spatial_audit.json` and `public_model_attempt.json` make the
non-identifiability explicit.

## Historical catalogue audit

`openaq_pm25_catalog_audit.csv` checked all 14 current Israeli PM2.5 locations
for 2016-2019 S3 objects. Only location `1285358` had objects. The three
current PM10 locations had zero objects, as retained in
`openaq_pm10_catalog_audit.csv`. All 119 current NO2 locations had S3 objects
in 2017-2019, but none had 2016 objects; see
`openaq_no2_catalog_audit.csv` and `openaq_no2_catalog_audit.json`.

## Closest public measured-pollutant model

AERIS reconstructed municipal 2018 NO2 with the same tool contract used for
PM2.5. `aeris_no2_2018.csv` contains 189 municipal assignments from 66 stations.
After the pre-specified coverage threshold of 180 daily values, the public
outcome model included 171 municipalities and 59 distinct exposure values.

The fitted standardized coefficient for 2018 NO2 was `-0.0016` (95% CI
`-0.1487` to `0.1455`; `p=0.983`; model R2 `0.101`). The complete input panel
and model result are saved in `no2_2018_public_model_panel.csv` and
`no2_2018_public_model_result.json`.

The paper reported a standardized NOx coefficient of `0.086` for July 24,
2020, using 2016-2019 NOx and additional covariates. OpenAQ provides NO2 with
no 2016 archive records, so this sensitivity model is retained separately from
the paper's PM2.5 and NOx effect estimates.

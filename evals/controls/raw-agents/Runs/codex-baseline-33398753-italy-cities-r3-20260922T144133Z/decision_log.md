# Decision log

- The article's principal analysis is cross-sectional log-log OLS: city COVID-19 cases in March/April 2020 on 2018 exceedance days and 2019 population density. The deposited data make 27 March and 7 April outcomes available; 7 April is the principal available outcome.
- The Mendeley workbook was sanitized by `code/sanitize_author_table.py`. Its `Days of Pollution` field was dropped before retained columns or rows were inspected. The retained/dropped names are in `derived/author_column_sanitization.json`.
- Exposure assignment was locked before data inspection: Nominatim capital geocode, nearest EEA PM10 station within 25 km, then annual count of daily means >50 ug/m3 with >=274 valid daily means. PM10-only is a disclosed substitution for the published PM10-or-ozone composite.
- The EEA ArcGIS station catalogue was retrieved. Agrigento's nearest PM10 station was IT1846A (AGRIGENTO_CENTRO), 1.145 km away. Its catalogue-advertised historical PM10 Parquet link returned HTTP 404, saved in `logs/eea_ag_pm10_404.txt`. This is a terminal other-4xx response under the retry policy, not a retriable transport failure.
- An alternate EEA portal/API search was saved in `raw/eea_api_root.html`, but did not supply the same downloadable daily series. Coverage therefore remained 0/55. No coverage criterion was relaxed and no model was fit.

Had the model run, each outcome date would report beta for a 1% higher annual exceedance count conditional on density, plus the positive outcome ratio `exp(beta * log(1.01))` and transformed CI. No coefficient was produced.

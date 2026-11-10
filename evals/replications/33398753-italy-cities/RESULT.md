# PMID 33398753: Italian provincial capitals

## Status

Fit completed.

## Public inputs

- Outcomes and density: the authors' openly licensed Mendeley workbook, downloaded from `https://data.mendeley.com/public-api/zip/bbnyhp6gfh/download/1`.
- Coordinates: GeoNames Italy gazetteer, downloaded from `https://download.geonames.org/export/dump/IT.zip`.
- Exposure: AERIS/OpenAQ daily PM10, 1 January through 31 December 2018.

The author-provided `Days of Pollution` column was not loaded into the analysis panel.

## Closest effect comparison

The paper's Table 6 model regresses log confirmed infections on 7 April 2020 on log 2018 days exceeding PM10 or ozone limits, adjusted for log population density. AERIS reconstructed PM10-only exceedance days above 50 ug/m3 and fit the same log-linear outcome and density specification.

| Quantity | Published | AERIS reconstruction |
| --- | ---: | ---: |
| PM10-related log coefficient | 0.813 | 0.800 |
| 95% CI | not reported in Table 6 | 0.174 to 1.426 |
| Analytic cities | 55 | 8 of 55 after >=75% daily PM10 coverage |
| Model R2 | 0.448 | 0.807 |

The reconstructed coefficient is stored in `effect_result.json`. The AERIS exposure panel and daily monitor values are stored in `aeris_pm10.csv` and `aeris_pm10_daily.csv`.

## Broad-coverage sensitivity

A second run used up to three stations within 250 km to assess whether a wider
assignment could recover more cities. It recovered daily exposure records for
51 cities; 46 met the same 75% coverage and nonzero-exceedance rules. The
coefficient was 0.328 (95% CI 0.013 to 0.644), or an outcome ratio of 1.26
(1.01 to 1.56) per doubling. The large radius changes the local exposure
definition, so this result is retained as a sensitivity analysis and does not
replace the strict reconstruction in the benchmark table.

The executable model is `fit_full_coverage_effect.py`; its output is
`effect_result_full_coverage.json`, with inputs in
`aeris_pm10_full_coverage_daily.csv` and `analysis_panel_full_coverage.csv`.

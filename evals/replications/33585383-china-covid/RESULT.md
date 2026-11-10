# Result: China COVID-19 and PM2.5

## Reconstruction run

The completed AERIS/OpenAQ output supports two prefectures: Beijing and
Langfang. Their public COVID-19 mortality values are 1.361% and 0.000%,
respectively. Beijing has 309 observed exposure days from 2014 and partial
2015, with a combined PM2.5 mean of 74.83 ug/m3. Langfang has 240 observed
days from 2014, with a PM2.5 mean of 82.91 ug/m3. No completed 2016 export
exists.

## Fit

The planned unadjusted Kendall tau-b test was run on the completed panel. Its
effect estimate is -1.00 because the two reconstructed PM2.5 values rank in
the reverse order of mortality. Two prefectures cannot support a meaningful
significance test or a 95% confidence interval.

| Quantity | Result |
| --- | --- |
| Completed analysis sample | 2 prefectures |
| Exposure years represented | 2014; partial 2015 for Beijing |
| Unique reconstructed PM2.5 values | 2 |
| Kendall tau-b | -1.00 |
| 95% confidence interval | Not estimable |
| Published comparison | tau-b = 0.18; n = 287 |

`analysis_panel.csv` and `model_result.json` contain the exact model inputs
and machine-readable result. This run is an attempted reconstruction and is
excluded from effect-calibration summaries.

# UK COVID-19 Replication Record

Study: PMID 38182658, *Association of air pollution and weather conditions during infection course with COVID-19 case fatality rate in the United Kingdom*.

## Inputs

- Outcomes: official UKHSA archived nation-day cases and deaths, recorded in `../../data-acquisition/38182658-uk-covid/`.
- Exposure: AERIS/OpenAQ daily PM2.5 network mean within the pinned UK nation polygons in `boundaries.geojson`.
- Weather: ECA&D blended daily station observations. `build_ecad_weather.py` creates nation-day temperature and sunshine series; the downloaded archives remain local under `weather-source/` and are intentionally excluded from Git.

## Results

| Model | Nation-days | PM2.5 ratio per 10 ug/m3 | 95% CI |
| --- | ---: | ---: | --- |
| PM2.5 plus nation fixed effects | 635 | 1.73 | 1.39 to 2.14 |
| PM2.5 plus ECA&D temperature, sunshine, and nation fixed effects | 635 | 1.46 | 1.21 to 1.76 |
| Published PM2.5 contrast | - | approximately 1.13 per 10 ug/m3 | 1.09 to 1.16 for 19 versus 10 ug/m3 |

The weather-adjusted AERIS estimate is the current comparison result.

## Re-run

```bash
python run_aeris_tools.py
python build_ecad_weather.py
python fit_exploratory_model.py
```

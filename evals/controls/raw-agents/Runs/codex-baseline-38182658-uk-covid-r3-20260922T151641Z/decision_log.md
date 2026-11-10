# Decision log

- The target was identified from PMID 38182658 as country-day instantaneous COVID-19 case-fatality probability in England, Northern Ireland, Scotland, and Wales, 26 March--15 September 2020.
- The selected published air-pollution predictor was PM2.5. The published selected model also included temperature, sunlight duration, humidity, weekday, and a country effect, with a 10-day exposure lag horizon.
- Exposure was independently constructed from Open-Meteo's air-quality endpoint (CAMS model output), at country-centroid coordinates and aggregated from hourly to daily arithmetic means. No author pollution table, code, or derived field was used.
- The public OWID outcome release was sanitized before inspection: only location, date, new_cases, and new_deaths were retained. The retained four constituent-country rows contain no nonmissing daily case or death measures; this is recorded in `source_manifest.json` and `health_outcomes_sanitized.csv`.
- UK aggregate observations were not substituted for the four-country statistical unit. Consequently, no iCFR reconstruction or binomial/DLNM model was fit.
- A browser/API attempt to the former UK Coronavirus Dashboard endpoint failed DNS resolution (`api.coronavirus.data.gov.uk`); its terminal error is retained in `failed_endpoint_evidence.txt`. It was not blindly retried because the service endpoint is retired/unresolvable in this environment.

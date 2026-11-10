# AERIS reproduction: Alaska wildfire proximity and asthma (PMID 38249516)

## Aim

This run reconstructs PM2.5 through AERIS/OpenAQ for the paper's Alaska Behavioral Health System (BHS) regions. The original study used wildfire proximity rather than monitor-based PM2.5, so this is an exposure-source substitution.

## Published analysis

The paper uses 11 BHS regions and years 2007--2017. It multiplies the annual age-adjusted adult current-asthma prevalence from Alaska BRFSS by the region's fixed 2010 population, then computes Pearson correlations with the number of people living near wildfire perimeters. It reports correlations from 0.75 at a five-mile buffer to about 0.94 at 25 miles.

## Independent analysis specified here

1. Build the 11 BHS regions from their documented 2010 borough/census-area membership.
2. Use 2010 Census Gazetteer populations and internal points to create reproducible regional AERIS subjects.
3. Reconstruct 2007--2017 PM2.5 through AERIS and retain strict and broad-assignment coverage diagnostics.
4. Extract the annual, age-adjusted BHS current-asthma estimates from the cited public Alaska BRFSS source.
5. Fit the paper's correlation only after both inputs support an annual regional panel.

## Public routes accessed

All routes are recorded in `sources.csv`, with UTC access timestamps and local output paths after execution.

- Paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC10798235/
- Alaska BRFSS Data Center: https://alaska-dph.shinyapps.io/BRFSS/
- Alaska BHS geography: https://health.alaska.gov/en/education/alaska-health-data-geographic/
- 2010 Census SF1 API: https://api.census.gov/data/2010/dec/sf1.html
- AICC fire-history data: https://fire.ak.blm.gov/predsvcs/maps.php
- AERIS source checkout: `.`, branch `agent-first-mcp`.

## Reproduction status

Input acquisition and model execution are recorded in `RESULT.md` and
`REPLICATION.md`. No fitted estimate is reported until the public outcome and
annual PM2.5 panel are both present.

## Run order

```bash
python scripts/acquire_geography.py
python scripts/reconstruct_pm25.py
python scripts/fit_analysis.py
```

`reconstruct_pm25.py` requires the AERIS environment, including `OPENAQ_API_KEY`, and writes its cache locally under `outputs/`.

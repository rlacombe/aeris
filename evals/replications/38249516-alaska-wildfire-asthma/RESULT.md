# Result: no fitted correlation

## Published target

Smith and Chi (2023; PMID 38249516) calculated annual adult current-asthma
counts for 11 Alaska BHS regions in 2007--2017. They multiplied annual,
age-adjusted regional BRFSS prevalence by a fixed 2010 population and reported
Pearson correlations of 0.75 to about 0.94 with wildfire-proximity exposure.

## Outcome-source result

No directly downloadable public outcome route was found for the annual,
age-adjusted current-asthma estimates by BHS region for 2007--2017.

The study cites the former Alaska ``Informed Alaskans'' BHS display. Its
successor, the Alaska BRFSS Data Center, is public in principle but its live
session did not return the asthma topic or a download link. The State's BRFSS
access page states that specialized datasets require a staff data request.
The statewide CDC BRFSS public-use files cannot replace this table because
they do not provide the Alaska BHS reporting geography. No outcome file was
downloaded and no correlation was fitted.

- Data Center: https://alaska-dph.shinyapps.io/BRFSS/
- Official access policy: https://health.alaska.gov/en/services/request-brfss-data/
- Accessed: 2026-08-15

## Public inputs obtained

- `inputs/paper.pdf`: open paper copy, downloaded from the NSF public-access
  repository.
- `inputs/2010_Gaz_counties_national.txt`: public 2010 Census Gazetteer.
- `outputs/bhs_region_membership.csv`: 27 historical county equivalents mapped
  to the 11 BHS regions.
- `outputs/bhs_region_subjects.csv`: population-weighted Census internal-point
  coordinates and fixed 2010 populations for the 11 AERIS subjects.

The cited public BHS table is no longer available at its original address. The
current Alaska BRFSS Data Center still exposes the regional geography but its
live public session did not populate the asthma topic or historical-table
download after acceptance of the displayed public-data agreement. The session
probe is retained in `outputs/brfss_transport_probe.json` and its executable
script is `scripts/probe_brfss_transport.py`.

## AERIS PM2.5 reconstruction

### Strict assignment: 25 km

`outputs/strict_25km_aeris_pm25.csv` contains three returned regions:
Anchorage, Fairbanks, and Juneau. Each has about 15% daily completeness across
the 4,018-day study window. The remaining eight BHS-region subjects have no
OpenAQ monitor within 25 km. The daily records, tool trace, run summary, and
diagnostic plots are all retained with the `strict_25km_` prefix.

### Broad-assignment sensitivity: 1,000 km catalog search

`outputs/wide_1000km_aeris_pm25.csv` contains all 11 regions. AERIS selected
the nearest monitor from the public US OpenAQ catalog and recovered data from
OpenAQ v3 plus the public S3 archive. Returned rows contain 603--618 daily
values per region, about 15.0--15.4% coverage. Eight assignments are more than
25 km away; the largest distance is 693.5 km. The complete tool trace is
`wide_1000km_aeris_tool_trace.json`. The current `get_daily_data` export
contains 500 records per subject (5,500 rows); the returned AERIS summary
records 603--618 measurements per subject and is the authoritative coverage
diagnostic for this run.

## Fit status

Not fitted. No downloadable BHS asthma outcome table is currently available.
The AERIS record also has about 15% daily coverage in each region and cannot
support annual PM2.5 means.

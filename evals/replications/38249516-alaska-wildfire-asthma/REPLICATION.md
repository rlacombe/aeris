# Alaska wildfire and asthma correlation: execution record

## Target

PMID 38249516 reports Pearson correlations between annual counts of adults
with current asthma and wildfire-proximity exposure across 11 Alaska BHS
regions from 2007 through 2017.

## Requested public outcome

Annual age-adjusted adult current-asthma prevalence for each BHS region and
year. The paper converts prevalence to counts using the fixed 2010 regional
population.

## Public source check

On 2026-08-15, `scripts/probe_brfss_transport.py` opened the public Alaska
BRFSS Data Center, accepted its displayed public-data agreement, and selected
the Single Indicator view. The portal retained a live Shiny session but did
not populate `SelectTopic`; it therefore exposed no asthma-table download.
The recorded browser state is `outputs/brfss_transport_probe.json`.

## Exposure check

`scripts/reconstruct_pm25.py` ran AERIS for the 11 BHS subjects over the full
study period. The broad 1,000 km search assigned all subjects, but returned
only 603--618 of 4,018 daily values per subject. These data do not support
annual regional PM2.5 estimates.

## Outcome

No model was fitted. The required public outcome export and an annual AERIS
exposure panel were both unavailable.

# Article and Source Review Prompt

You are reviewing one public-health article for inclusion in an AERIS
source-substitution reanalysis benchmark. Read the article's Methods and data-
availability information. Then inspect the original public source named by the
article. Do not decide eligibility from the title or abstract alone.

Return a structured review with the following fields:

1. Citation and persistent identifier.
2. Ambient pollutant and exposure type. Include wildfire smoke or desert dust
   when the study estimates ambient criteria-pollutant exposure.
3. Health outcome and its stated source.
4. A direct download URL, public portal route, or reproducible public-query
   route for the outcome data.
5. Whether retrieval requires an account, request, agreement, approval, or
   collaborator.
6. Date or time key, geographic key, and whether each is available from the
   public outcome route.
7. The reported primary analysis and required non-exposure covariates.
8. Whether AERIS can independently construct an ambient exposure record from
   public sources for the stated pollutant, period, and geography.
9. A decision: retain for execution, exclude, or unresolved. State one concise
   reason and identify any required implementation adapter.

Use the paper and primary source as evidence. Quote URLs and field names where
available. Record uncertainty explicitly; do not infer data availability from a
publisher landing page alone.

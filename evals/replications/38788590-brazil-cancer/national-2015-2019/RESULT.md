# Result

Status: completed national source-substitution reconstruction.

## Completed exposure retrieval

The first full-window AERIS request returned 100 daily values in 2017 because
the public S3 archive guardrail limits one request to 400 days. The audited
annual AERIS strategy then issued five calendar-year requests. It recovered
100 daily national monitor-network PM2.5 values in 2017 and none in 2015,
2016, 2018, or 2019.

The current AERIS/OpenAQ record contains 18 PM2.5 monitor locations and 100
of 1,826 calendar days (5.48%). It cannot support the planned five-year
case-crossover fit. The full AERIS trace is
`data/derived/aeris_national_tool_trace.json`.

## Public-monitor recovery

The IEMA archive recovery supplies all 1,826 study days. It contains 79,440
station-day means from Ceará, Espírito Santo, Minas Gerais, Rio de Janeiro,
and São Paulo. Each daily network mean uses 15--84 stations (median 45) and
three to five states (median four). The IEMA series is the record used for the
national fit once SIM ingestion finishes.

## National estimate

Brazil, 2015--2019: **OR 1.060** per 10 ug/m3 PM2.5 (95% CI
1.052--1.069). The paper reports OR 1.01 per 10 ug/m3 for the same five-year
window.

The fitted panel contains 1,824 complete lagged days, 929,790 cancer deaths,
and 1,824 case dates. The conditional-score norm divided by total case weight
is `5.34e-10`; the minimum information-matrix eigenvalue is `18,636.43`.

The result uses the IEMA public-monitor recovery and weather averaged across
the capitals of its contributing states. `outputs/effect_result_iema.json`
contains the fitted coefficients and diagnostics.

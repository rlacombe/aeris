# Blocker ledger

No terminal blocker prevented fitting the reconstructed principal comparison.

| Item | Evidence | Handling | Effect |
| --- | --- | --- | --- |
| United States physician covariate unavailable in the article's 2015–2017 World Bank selection window | `analysis_panel.csv` has missing `physicians_per_1000` for USA; raw `SH.MED.PHYS.ZS.json` preserves source response | Complete-case OLS; no imputation or unrecorded source substitution | 35 rather than 36 countries per model |
| Historical COVID data differ from WHO 2020 snapshots | Paper specifies WHO reports; outcome source and retrieval checksum are documented in `source_manifest.json` | Declared public-source substitution to OWID historical series | Estimates are an independent reconstruction, not an exact snapshot replication |
| Original GDP unit not stated | Article table labels GDP but does not specify its numerical unit | Total 2019 current USD from World Bank, divided by 1e9, predeclared in code | Coefficient scale for GDP differs; PM2.5 coefficient is conditional on this documented specification |

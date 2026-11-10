# Reproduction Record

## Execution

```bash
python build_atlas_proxy_panel.py
python run_aeris_tools.py
python build_adjusted_public_panel.py
python fit_adjusted_public_model.py
```

The completed model uses the stored AERIS run. It selected 303 county
centroids, returned 47 annual PM2.5 records with at least 50% completeness, and
fit 46 counties after the public covariate join.

## Input and Output Checksums

| File | SHA-256 |
|---|---|
| `atlas_all_stroke_65plus_county_2019.csv` | `202b79b37bd9d63a38912a25481068f5103588e734bd8887bd90c29ea38bdf61` |
| `aeris_pm25_2019_systematic_10pct.csv` | `7bc2f4ab20856eeb8b44e25683ec2ce61be43da0777d9b100b51cb7392f17287` |
| `cdc_places_2019_stroke_covariates.json` | `f2e485b59f46ca891ebfa0993e1eb16f03ddea74923b057ecc98df8bea78835d` |
| `chr_2020_analytic_data.csv` | `bd355c2bf87326acfe29221cc77fbe932d9cabdc59090daad43ca9b8b2e851a3` |
| `adjusted_public_analysis_panel.csv` | `932c9b2d80f1aaca8543d4ea2e981403d4bfc5f41c49bd7218b2b051c62782c0` |
| `adjusted_public_model_coefficients.csv` | `b58d78e7d1f83fb62454ecc2f99dfd85f8e0cebc8ab854901bbd47a2ed136ae3` |
| `adjusted_public_model_result.json` | `fdcca9096d78aaa480c60d439e16128e8d9c455aeb2bed4e9c806a0bf0615f25` |

## Study-Frame Differences

The published model uses a 2016--2020 ischemic-stroke outcome. The public CDC
Atlas export provides a 2019 all-stroke outcome for adults 65+. The exposure
record uses 2019 AERIS/OpenAQ PM2.5. County Health Rankings supplies a
child-poverty proxy and access-to-exercise proxy for the paper's poverty and
park-access covariates. The result file records each difference.

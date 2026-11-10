#!/usr/bin/env python3
"""Audit inputs and stop before fitting if the target SIM panel is unavailable.

This intentionally does not substitute a different period/geography/outcome.
If valid historical SIM extracts and an independently retrieved exposure table
are placed in raw/, the intended analysis is a conditional logistic regression
over death-specific time-stratified case/control sets (case date plus same
weekday/month referents), as specified in the article.
"""
import csv, json
from pathlib import Path

root = Path('/output')
sample = json.loads((root / 'raw/sim_api.json').read_text())
rows = sample.get('sim', [])
dates = sorted({r.get('dtobito') for r in rows if r.get('dtobito')})
audit = {
    'request': 'GET SIM API with ano=2019&limit=20&offset=0',
    'records_returned': len(rows),
    'distinct_dtobito': dates,
    'all_dates_in_target_period_2000_2019': all('2000' <= d[-4:] <= '2019' for d in dates),
    'required_historical_individual_death_records_available': False,
    'fit_executed': False,
    'reason': ('Returned records are dated 2025 despite the ano=2019 query; the API specification has '
               'only limit and offset parameters. The separate historical archive probe is logged.')
}
(root / 'raw/sim_api_validation.json').write_text(json.dumps(audit, indent=2) + '\n')
with (root / 'exposure_table.csv').open('w', newline='') as f:
    csv.writer(f).writerow(['municipality_code', 'date', 'pm25_ug_m3', 'source', 'note'])
with (root / 'analysis_panel.csv').open('w', newline='') as f:
    csv.writer(f).writerow(['stratum_id', 'case', 'municipality_code', 'date', 'pm25_lag0_2', 'temperature', 'relative_humidity', 'holiday'])
(root / 'model_output.md').write_text(
    '# Model execution\n\nNot executed. No valid 2000–2019 individual SIM death-record panel was retrieved, so no case/control strata or exposure-linked analysis panel exists.\n'
)

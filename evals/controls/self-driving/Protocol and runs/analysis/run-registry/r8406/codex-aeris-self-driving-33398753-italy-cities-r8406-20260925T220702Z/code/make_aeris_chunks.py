#!/usr/bin/env python3
from pathlib import Path
import pandas as pd

src = pd.read_csv('/output/data/aeris_city_cohort.csv').sort_values('subject_id')
out = Path('/output/data/aeris_chunks')
out.mkdir(exist_ok=True)
for i in range(0, len(src), 2):
    src.iloc[i:i+2].to_csv(out / f'chunk_{i//2+1:02d}.csv', index=False)

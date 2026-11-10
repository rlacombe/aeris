#!/usr/bin/env python3
"""Sanitize author-designated data before any retained data are inspected."""
import csv, json, re
from pathlib import Path
import openpyxl

SRC=Path('/output/raw/author_table.xlsx')
OUT=Path('/output/derived')
pollution=re.compile(r'(pollution|pm\s*10|pm10|ozone|exceed)',re.I)
wb=openpyxl.load_workbook(SRC,read_only=True,data_only=True)
ws=wb['Data ']
headers=[ws.cell(1,i).value for i in range(1,ws.max_column+1)]
dropped=[h for h in headers if pollution.search(str(h or ''))]
retained=[h for h in headers if h not in dropped]
with open(OUT/'author_column_sanitization.json','w') as f:
    json.dump({'source':str(SRC),'sheet':'Data ','rule':pollution.pattern,
               'dropped_columns':dropped,'retained_columns':retained},f,indent=2)
with open(OUT/'author_sanitized.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=retained); w.writeheader()
    for row in ws.iter_rows(min_row=2,values_only=True):
        d=dict(zip(headers,row)); w.writerow({h:d[h] for h in retained})

#!/usr/bin/env python3
"""Download the county ischemic-stroke outcome for PMID 39377000 from CDC WONDER.

The script submits a single public Underlying Cause of Death 1999--2020
(D76) query. It groups by county, selects deaths of people aged 65 or older,
and returns deaths, population, and crude rate for ICD-10 I63 in 2016--2020.
"""

from __future__ import annotations

import csv
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


RUN_DIR = Path(__file__).resolve().parent
ENDPOINT = "https://wonder.cdc.gov/controller/datarequest/D76"
YEARS = ["2016", "2017", "2018", "2019", "2020"]


def parameter(name: str, value: str) -> str:
    return f"<parameter><name>{name}</name><value>{value}</value></parameter>"


def parameters(name: str, values: list[str]) -> str:
    return "".join(parameter(name, value) for value in values)


def request_xml() -> str:
    groups = {
        "B_1": "D76.V9-level2",  # County
        "B_2": "D76.V1-level1",  # Year
        "B_3": "*None*",
        "B_4": "*None*",
        "B_5": "*None*",
    }
    measures = {
        "M_1": "D76.M1",  # deaths
        "M_2": "D76.M2",  # population
        "M_3": "D76.M3",  # crude rate
        "M_31": "D76.M31",  # crude-rate standard error
        "M_32": "D76.M32",  # crude-rate confidence interval
    }
    finder = {
        "F_D76.V1": YEARS,
        "F_D76.V10": ["*All*"],
        "F_D76.V2": ["I63"],  # cerebral infarction (ischemic stroke)
        "F_D76.V27": ["*All*"],
        "F_D76.V9": ["*All*"],
    }
    selected = {
        "I_D76.V1": "2016;2017;2018;2019;2020",
        "I_D76.V10": "*All* (The United States)",
        "I_D76.V2": "I63 (Cerebral infarction)",
        "I_D76.V27": "*All* (The United States)",
        "I_D76.V9": "*All* (The United States)",
    }
    limits: dict[str, str | list[str]] = {
        "V_D76.V1": "",
        "V_D76.V10": "",
        "V_D76.V11": "*All*",
        "V_D76.V12": "*All*",
        "V_D76.V17": "*All*",
        "V_D76.V19": "*All*",
        "V_D76.V2": "",
        "V_D76.V20": "*All*",
        "V_D76.V21": "*All*",
        "V_D76.V22": "*All*",
        "V_D76.V23": "*All*",
        "V_D76.V24": "*All*",
        "V_D76.V25": "*All*",
        "V_D76.V27": "",
        "V_D76.V4": "*All*",
        "V_D76.V5": ["65-74", "75-84", "85+"],
        "V_D76.V51": "*All*",
        "V_D76.V52": "*All*",
        "V_D76.V6": "00",
        "V_D76.V7": "*All*",
        "V_D76.V8": "*All*",
        "V_D76.V9": "",
    }
    other = {
        "action-Send": "Send",
        "finder-stage-D76.V1": "codeset",
        "finder-stage-D76.V2": "codeset",
        "finder-stage-D76.V27": "codeset",
        "finder-stage-D76.V9": "codeset",
        "stage": "request",
        "accept_datause_restrictions": "true",
    }

    values = []
    for mapping in (groups, measures, selected, other):
        values.extend(parameter(name, value) for name, value in mapping.items())
    for mapping in (finder, limits):
        for name, value in mapping.items():
            values.append(parameters(name, value) if isinstance(value, list) else parameter(name, value))
    return "<request-parameters>" + "".join(values) + "</request-parameters>"


def main() -> int:
    xml = request_xml()
    (RUN_DIR / "wonder_request.xml").write_text(xml, encoding="utf-8")
    body = urllib.parse.urlencode(
        {"request_xml": xml, "accept_datause_restrictions": "true"}
    ).encode()
    request = urllib.request.Request(ENDPOINT, data=body, method="POST")
    with urllib.request.urlopen(request, timeout=180) as response:
        raw = response.read()
    (RUN_DIR / "wonder_response.xml").write_bytes(raw)

    root = ET.fromstring(raw)
    errors = [node.text for node in root.findall(".//error-message") if node.text]
    if errors:
        raise RuntimeError("CDC WONDER returned an error: " + " | ".join(errors))

    rows = []
    for row in root.findall(".//data-table//r"):
        rows.append([cell.text or "" for cell in row.findall("./c")])
    if not rows:
        raise RuntimeError("CDC WONDER returned no data rows; inspect wonder_response.xml")
    with (RUN_DIR / "wonder_ischemic_stroke_county_year_2016_2020.tsv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        csv.writer(handle, delimiter="\t").writerows(rows)
    print(f"Wrote {len(rows)} county-year rows")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # Preserve server response for audit.
        print(error, file=sys.stderr)
        raise SystemExit(1)

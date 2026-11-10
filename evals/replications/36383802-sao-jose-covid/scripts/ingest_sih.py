#!/usr/bin/env python3
"""Decode SIH/SUS RD files and form the paper-defined daily B34.2 series."""

from __future__ import annotations

import json
import struct
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / ".vendor"
sys.path.insert(0, str(VENDOR))
import datasus_dbc  # noqa: E402

RAW = ROOT / "data" / "raw" / "sih"
DERIVED = ROOT / "data" / "derived"
START, END = "2020-04-01", "2021-04-30"
MUNICIPALITY = "354990"


def clean(value: object) -> str:
    return "" if value is None else str(value).strip().upper()


def parse_date(value: object) -> str | None:
    raw = "".join(char for char in clean(value) if char.isdigit())
    if len(raw) != 8:
        return None
    try:
        return datetime.strptime(raw, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def iter_records(dbf: bytes, requested: set[str]):
    count = struct.unpack_from("<I", dbf, 4)[0]
    header_size = struct.unpack_from("<H", dbf, 8)[0]
    row_size = struct.unpack_from("<H", dbf, 10)[0]
    fields: list[tuple[str, int, int]] = []
    offset, position = 32, 1
    while offset < header_size and dbf[offset] != 0x0D:
        descriptor = dbf[offset : offset + 32]
        name = descriptor[:11].split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
        width = descriptor[16]
        if name in requested:
            fields.append((name, position, width))
        position += width
        offset += 32
    found = {name for name, _, _ in fields}
    if found != requested:
        raise RuntimeError(f"Missing SIH fields: {sorted(requested - found)}")
    for index in range(count):
        row = dbf[header_size + index * row_size : header_size + (index + 1) * row_size]
        if len(row) != row_size:
            raise RuntimeError("DBF ended before its stated record count")
        if row[:1] != b"*":
            yield {name: row[start : start + width].decode("latin1", errors="ignore").strip() for name, start, width in fields}


def main() -> int:
    files = sorted(RAW.glob("RDSP*.dbc"))
    if len(files) != 13:
        raise RuntimeError(f"Expected 13 monthly SIH files; found {len(files)}")
    DERIVED.mkdir(parents=True, exist_ok=True)
    admissions, deaths, totals = Counter(), Counter(), Counter()
    for file in files:
        dbf = datasus_dbc.decompress_bytes(file.read_bytes())
        for row in iter_records(dbf, {"MUNIC_RES", "DT_INTER", "DIAG_PRINC", "MORTE"}):
            totals["records_read"] += 1
            if clean(row["MUNIC_RES"])[:6] != MUNICIPALITY:
                continue
            totals["municipality_records"] += 1
            if clean(row["DIAG_PRINC"]).replace(".", "") != "B342":
                continue
            totals["b342_records"] += 1
            day = parse_date(row["DT_INTER"])
            if day is None or not START <= day <= END:
                totals["invalid_or_out_of_window_date"] += 1
                continue
            admissions[day] += 1
            deaths[day] += int(clean(row["MORTE"]) == "1")
    days = pd.date_range(START, END, freq="D")
    frame = pd.DataFrame({"date": days.strftime("%Y-%m-%d")})
    frame["covid_admissions"] = frame["date"].map(admissions).fillna(0).astype(int)
    frame["in_hospital_deaths"] = frame["date"].map(deaths).fillna(0).astype(int)
    output = DERIVED / "sih_daily_b342_admissions.csv"
    frame.to_csv(output, index=False)
    summary = {
        "input_files": [file.name for file in files],
        "municipality_ibge": MUNICIPALITY,
        "diagnosis": "B34.2",
        "observation_window": [START, END],
        "counts": dict(totals),
        "admissions": int(frame.covid_admissions.sum()),
        "deaths": int(frame.in_hospital_deaths.sum()),
        "days": len(frame),
        "output": str(output),
    }
    (DERIVED / "sih_ingestion_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())

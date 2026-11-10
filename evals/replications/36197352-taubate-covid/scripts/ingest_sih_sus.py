#!/usr/bin/env python3
"""Decode SIH/SUS microdata into daily B34.2 admissions for the study area."""

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
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))
import datasus_dbc  # noqa: E402

RAW = ROOT / "data" / "raw" / "sih_sus"
DERIVED = ROOT / "data" / "derived"
MUNICIPALITIES = {"355410", "355480", "353800"}
START = "2020-04-01"
END = "2021-03-31"


def fields_from_dbf(dbf: bytes, required: set[str]):
    count = struct.unpack_from("<I", dbf, 4)[0]
    header = struct.unpack_from("<H", dbf, 8)[0]
    record_length = struct.unpack_from("<H", dbf, 10)[0]
    offset, position, found = 32, 1, []
    while offset < header and dbf[offset] != 0x0D:
        descriptor = dbf[offset:offset + 32]
        name = descriptor[:11].split(b"\x00", 1)[0].decode("ascii", "ignore").strip()
        width = descriptor[16]
        if name in required:
            found.append((name, position, width))
        position += width
        offset += 32
    missing = required - {name for name, _, _ in found}
    if missing:
        raise RuntimeError(f"SIH schema lacks fields: {sorted(missing)}")
    for index in range(count):
        row = dbf[header + index * record_length:header + (index + 1) * record_length]
        if len(row) != record_length or row[:1] == b"*":
            continue
        yield {name: row[start:start + width].decode("latin1", "ignore").strip() for name, start, width in found}


def admission_date(value: str) -> str | None:
    digits = "".join(char for char in value if char.isdigit())
    if len(digits) != 8:
        return None
    try:
        return datetime.strptime(digits, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def municipality(value: str) -> str:
    return "".join(char for char in value if char.isdigit())[:6]


def main() -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    counts: Counter[str] = Counter()
    audit: Counter[str] = Counter()
    file_summaries = []
    for path in sorted(RAW.glob("RDSP*.dbc")):
        decoded = datasus_dbc.decompress_bytes(path.read_bytes())
        file_audit = Counter()
        for row in fields_from_dbf(decoded, {"MUNIC_RES", "DT_INTER", "DIAG_PRINC"}):
            file_audit["records"] += 1
            if municipality(row["MUNIC_RES"]) not in MUNICIPALITIES:
                continue
            file_audit["resident_area"] += 1
            if row["DIAG_PRINC"].replace(".", "").upper() != "B342":
                continue
            day = admission_date(row["DT_INTER"])
            if day is None or not (START <= day <= END):
                file_audit["invalid_or_outside_period"] += 1
                continue
            counts[day] += 1
            file_audit["selected"] += 1
        audit.update(file_audit)
        file_summaries.append({"file": path.name, **file_audit})
    dates = pd.date_range(START, END, freq="D")
    frame = pd.DataFrame({"date": dates.strftime("%Y-%m-%d")})
    frame["admissions_b342"] = frame["date"].map(counts).fillna(0).astype(int)
    output = DERIVED / "sih_sus_daily_b342.csv"
    frame.to_csv(output, index=False)
    summary = {"municipality_residence_codes": sorted(MUNICIPALITIES), "date_range": [START, END], "counts": dict(audit), "n_admissions": int(frame["admissions_b342"].sum()), "n_days": len(frame), "files": file_summaries, "output": str(output)}
    (DERIVED / "sih_sus_ingestion.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

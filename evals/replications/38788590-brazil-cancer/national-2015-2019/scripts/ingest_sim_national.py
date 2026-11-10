#!/usr/bin/env python3
"""Derive daily national cancer deaths from downloaded SIM DBC files."""
from __future__ import annotations

import json
import struct
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent
VENDOR = PARENT / ".vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))
import datasus_dbc  # noqa: E402

RAW = ROOT / "data" / "raw" / "sim"
DERIVED = ROOT / "data" / "derived"
YEARS = range(2015, 2020)
CANCER_RANGES = (("C00", "C10"), ("C12", "C14"), ("C11", "C11"), ("C15", "C15"), ("C16", "C16"), ("C18", "C21"), ("C22", "C22"), ("C23", "C24"), ("C25", "C25"), ("C32", "C32"), ("C33", "C34"), ("C40", "C41"), ("C43", "C43"), ("C50", "C50"), ("C53", "C53"), ("C54", "C55"), ("C56", "C56"), ("C61", "C61"), ("C62", "C62"), ("C64", "C66"), ("C67", "C67"), ("C70", "C72"), ("C81", "C85"), ("C91", "C95"))


def selected(code: object) -> bool:
    value = "" if code is None else str(code).strip().upper().replace(".", "")[:3]
    return len(value) == 3 and any(start <= value <= end for start, end in CANCER_RANGES)


def date_for(value: object) -> str | None:
    text = "" if value is None else "".join(char for char in str(value) if char.isdigit())
    try:
        return datetime.strptime(text, "%d%m%Y").date().isoformat() if len(text) == 8 else None
    except ValueError:
        return None


def records(dbf: bytes):
    if len(dbf) < 33:
        raise RuntimeError("Decoded SIM DBC payload is not a DBF.")
    count = struct.unpack_from("<I", dbf, 4)[0]
    header = struct.unpack_from("<H", dbf, 8)[0]
    record_size = struct.unpack_from("<H", dbf, 10)[0]
    fields, position, offset = {}, 1, 32
    while offset < header and dbf[offset] != 0x0D:
        descriptor = dbf[offset:offset + 32]
        name = descriptor[:11].split(b"\0", 1)[0].decode("ascii", errors="ignore").strip()
        width = descriptor[16]
        if name in {"DTOBITO", "CAUSABAS"}:
            fields[name] = (position, width)
        position += width
        offset += 32
    missing = {"DTOBITO", "CAUSABAS"} - set(fields)
    if missing:
        raise RuntimeError(f"Missing SIM fields: {sorted(missing)}")
    for index in range(count):
        row = dbf[header + index * record_size: header + (index + 1) * record_size]
        if len(row) != record_size:
            raise RuntimeError("Truncated DBF record")
        if row[:1] == b"*":
            continue
        yield {name: row[start:start + width].decode("latin1", errors="ignore").strip() for name, (start, width) in fields.items()}


def main() -> int:
    files = sorted(RAW.glob("DO??20*.dbc"))
    expected = 135
    if len(files) != expected:
        raise RuntimeError(f"Expected {expected} SIM state-year files; found {len(files)}. Run fetch_sim_national.py.")
    daily, by_file = Counter(), []
    for path in files:
        total = selected_count = 0
        print(f"Decoding {path.name}", flush=True)
        try:
            decoded = datasus_dbc.decompress_bytes(path.read_bytes())
        except Exception as exc:
            raise RuntimeError(f"Could not decode {path.name}; re-download this source file.") from exc
        for row in records(decoded):
            total += 1
            date = date_for(row["DTOBITO"])
            if date is not None and date[:4] in {str(year) for year in YEARS} and selected(row["CAUSABAS"]):
                daily[date] += 1
                selected_count += 1
        by_file.append({"file": path.name, "records": total, "selected_cancer_deaths": selected_count})
        (DERIVED / "sim_ingestion_progress.json").write_text(
            json.dumps({"completed_files": len(by_file), "last_completed_file": path.name}, indent=2) + "\n"
        )
    dates = pd.date_range("2015-01-01", "2019-12-31", freq="D")
    output = pd.DataFrame({"date": dates.strftime("%Y-%m-%d")})
    output["cancer_deaths"] = output.date.map(daily).fillna(0).astype(int)
    DERIVED.mkdir(parents=True, exist_ok=True)
    output.to_csv(DERIVED / "sim_national_daily_cancer_deaths.csv", index=False)
    summary = {"files": by_file, "n_files": len(files), "calendar_days": len(output), "selected_cancer_deaths": int(output.cancer_deaths.sum()), "days_with_deaths": int((output.cancer_deaths > 0).sum()), "cancer_ranges": CANCER_RANGES}
    (DERIVED / "sim_ingestion_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({key: summary[key] for key in ("n_files", "calendar_days", "selected_cancer_deaths", "days_with_deaths")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Decode public DATASUS SIM DBC data and derive daily paper-defined cancer deaths."""

from __future__ import annotations

import argparse
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


RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"

# Exact union stated in Yu et al. Methods 2.1. Ranges are inclusive ICD-10 prefixes.
CANCER_RANGES = (
    ("C00", "C10"), ("C12", "C14"), ("C11", "C11"), ("C15", "C15"),
    ("C16", "C16"), ("C18", "C21"), ("C22", "C22"), ("C23", "C24"),
    ("C25", "C25"), ("C32", "C32"), ("C33", "C34"), ("C40", "C41"),
    ("C43", "C43"), ("C50", "C50"), ("C53", "C53"), ("C54", "C55"),
    ("C56", "C56"), ("C61", "C61"), ("C62", "C62"), ("C64", "C66"),
    ("C67", "C67"), ("C70", "C72"), ("C81", "C85"), ("C91", "C95"),
)


def clean_text(value: object) -> str:
    return "" if value is None else str(value).strip().upper()


def municipality_matches(value: object, target: str) -> bool:
    observed = "".join(char for char in clean_text(value) if char.isdigit())
    return observed[:6] == target[:6]


def is_selected_cancer(value: object) -> bool:
    code = clean_text(value).replace(".", "")[:3]
    if len(code) != 3 or not code.startswith("C") or not code[1:].isdigit():
        return False
    return any(start <= code <= end for start, end in CANCER_RANGES)


def parse_date(value: object) -> str | None:
    raw = "".join(char for char in clean_text(value) if char.isdigit())
    if len(raw) != 8:
        return None
    try:
        return datetime.strptime(raw, "%d%m%Y").date().isoformat()
    except ValueError:
        return None


def iter_dbf_records(dbf: bytes, requested_fields: set[str]):
    """Yield requested dBASE III character fields directly from decoded bytes.

    DATASUS DBC decompresses to a regular DBF. Parsing only the three fields
    needed for this outcome avoids writing a much larger temporary DBF on a
    constrained workstation.
    """
    if len(dbf) < 33:
        raise RuntimeError("Decoded DBC payload is too short to be a DBF.")
    n_records = struct.unpack_from("<I", dbf, 4)[0]
    header_length = struct.unpack_from("<H", dbf, 8)[0]
    record_length = struct.unpack_from("<H", dbf, 10)[0]
    fields: list[tuple[str, int, int]] = []
    offset = 32
    record_offset = 1
    while offset < header_length and dbf[offset] != 0x0D:
        descriptor = dbf[offset : offset + 32]
        name = descriptor[:11].split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
        width = descriptor[16]
        if name in requested_fields:
            fields.append((name, record_offset, width))
        record_offset += width
        offset += 32
    found = {name for name, _, _ in fields}
    missing = requested_fields - found
    if missing:
        raise RuntimeError(f"SIM schema does not contain expected fields: {sorted(missing)}")
    for index in range(n_records):
        start = header_length + index * record_length
        end = start + record_length
        record = dbf[start:end]
        if len(record) != record_length:
            raise RuntimeError("DBF ended before its stated record count.")
        if record[:1] == b"*":
            continue
        yield {
            name: record[position : position + width].decode("latin1", errors="ignore").strip()
            for name, position, width in fields
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=RAW / "DOSP2019.dbc")
    parser.add_argument("--municipality-code", default="355030", help="Six-digit SIM municipality code.")
    parser.add_argument("--year", type=int, default=2019)
    args = parser.parse_args()

    if not args.input.exists():
        raise FileNotFoundError(f"Missing SIM input: {args.input}. Run fetch_sim.py first.")
    DERIVED.mkdir(parents=True, exist_ok=True)
    required = {"CODMUNRES", "DTOBITO", "CAUSABAS"}
    dbf = datasus_dbc.decompress_bytes(args.input.read_bytes())

    selected = Counter()
    totals = Counter()
    causes = Counter()
    for record in iter_dbf_records(dbf, required):
        totals["records_read"] += 1
        if not municipality_matches(record.get("CODMUNRES"), args.municipality_code):
            continue
        totals["municipality_records"] += 1
        date = parse_date(record.get("DTOBITO"))
        if date is None or not date.startswith(f"{args.year}-"):
            totals["invalid_or_out_of_year_dates"] += 1
            continue
        totals["valid_dated_municipality_records"] += 1
        if not is_selected_cancer(record.get("CAUSABAS")):
            continue
        selected[date] += 1
        causes[clean_text(record.get("CAUSABAS"))[:3]] += 1
        totals["selected_cancer_deaths"] += 1

    dates = pd.date_range(f"{args.year}-01-01", f"{args.year}-12-31", freq="D")
    daily = pd.DataFrame({"date": dates.strftime("%Y-%m-%d")})
    daily["cancer_deaths"] = daily["date"].map(selected).fillna(0).astype(int)
    output = DERIVED / "sim_daily_all_cancer.csv"
    daily.to_csv(output, index=False)
    summary = {
        "input": str(args.input),
        "decoded_dbf": "Decoded in memory; no temporary DBF written.",
        "municipality_code_sim": args.municipality_code,
        "year": args.year,
        "schema": sorted(required),
        "counts": dict(totals),
        "days_with_cancer_deaths": int((daily["cancer_deaths"] > 0).sum()),
        "selected_icd_prefix_counts": dict(sorted(causes.items())),
        "cancer_ranges": list(CANCER_RANGES),
        "output": str(output),
    }
    (DERIVED / "sim_ingestion_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

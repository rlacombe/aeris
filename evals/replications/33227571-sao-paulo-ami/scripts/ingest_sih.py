#!/usr/bin/env python3
"""Derive the paper-defined daily I21 admission series from public SIH/SUS files."""

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

RAW = ROOT / "data" / "raw"
DERIVED = ROOT / "data" / "derived"


def clean(value: object) -> str:
    return "" if value is None else str(value).strip().upper()


def parse_date(value: object) -> str | None:
    digits = "".join(char for char in clean(value) if char.isdigit())
    if len(digits) != 8:
        return None
    try:
        return datetime.strptime(digits, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def iter_records(dbf: bytes, requested: set[str]):
    n_records = struct.unpack_from("<I", dbf, 4)[0]
    header_length = struct.unpack_from("<H", dbf, 8)[0]
    record_length = struct.unpack_from("<H", dbf, 10)[0]
    fields = []
    offset, position = 32, 1
    while offset < header_length and dbf[offset] != 0x0D:
        descriptor = dbf[offset : offset + 32]
        name = descriptor[:11].split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()
        width = descriptor[16]
        if name in requested:
            fields.append((name, position, width))
        position += width
        offset += 32
    if set(name for name, _, _ in fields) != requested:
        raise RuntimeError(f"Missing SIH fields: {sorted(requested - set(name for name, _, _ in fields))}")
    for index in range(n_records):
        record = dbf[header_length + index * record_length : header_length + (index + 1) * record_length]
        if len(record) != record_length:
            raise RuntimeError("DBF ended before its stated record count")
        if record[:1] != b"*":
            yield {name: record[start : start + width].decode("latin1", errors="ignore").strip() for name, start, width in fields}


def main() -> int:
    DERIVED.mkdir(parents=True, exist_ok=True)
    municipalities = json.loads((RAW / "sao_paulo_metropolitan_municipalities.json").read_text())
    # SIH stores the six-digit municipal code, omitting IBGE's check digit.
    target_codes = {str(item["ibge_code"])[:6] for item in municipalities}
    daily = Counter()
    deaths = Counter()
    totals = Counter()
    requested = {"MUNIC_RES", "DT_INTER", "DIAG_PRINC", "MORTE"}
    for file in sorted((RAW / "sih").glob("RDSP*.dbc")):
        dbf = datasus_dbc.decompress_bytes(file.read_bytes())
        for record in iter_records(dbf, requested):
            totals["records_read"] += 1
            if clean(record["MUNIC_RES"])[:6] not in target_codes:
                continue
            totals["metro_resident_records"] += 1
            if not clean(record["DIAG_PRINC"]).replace(".", "").startswith("I21"):
                continue
            totals["i21_records"] += 1
            date = parse_date(record["DT_INTER"])
            if date is None or not ("2012-01-01" <= date <= "2015-12-31"):
                totals["invalid_or_out_of_window_date"] += 1
                continue
            daily[date] += 1
            deaths[date] += int(clean(record["MORTE"]) == "1")
    dates = pd.date_range("2012-01-01", "2015-12-31", freq="D")
    output = pd.DataFrame({"date": dates.strftime("%Y-%m-%d")})
    output["mi_admissions"] = output["date"].map(daily).fillna(0).astype(int)
    output["in_hospital_deaths"] = output["date"].map(deaths).fillna(0).astype(int)
    output.to_csv(DERIVED / "sih_daily_i21_admissions.csv", index=False)
    summary = {"target_ibge_municipalities": len(target_codes), "counts": dict(totals), "admissions": int(output.mi_admissions.sum()), "deaths": int(output.in_hospital_deaths.sum()), "days": len(output), "outcome_file": "data/derived/sih_daily_i21_admissions.csv"}
    (DERIVED / "sih_ingestion_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

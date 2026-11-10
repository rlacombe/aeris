#!/usr/bin/env python3
"""Atomically replace one SIM file only after a DBC decode succeeds."""
from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / ".vendor"))
import datasus_dbc  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="for example DOSP2015.dbc")
    args = parser.parse_args()
    if not args.file.startswith("DO") or not args.file.endswith(".dbc"):
        raise ValueError("Expected a SIM DBC filename.")
    output = ROOT / "data" / "raw" / "sim" / args.file
    url = f"https://datasus-ftp-mirror.nyc3.digitaloceanspaces.com/SIM/CID10/DORES/{args.file}"
    replacement = output.with_suffix(".validated.partial")
    request = urllib.request.Request(url, headers={"User-Agent": "AERIS-reproduction/1.0"})
    with urllib.request.urlopen(request, timeout=300) as response:
        replacement.write_bytes(response.read())
    decoded = datasus_dbc.decompress_bytes(replacement.read_bytes())
    if len(decoded) < 1024:
        raise RuntimeError("Validated decode is implausibly small.")
    replacement.replace(output)
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    print({"file": args.file, "source": url, "bytes": output.stat().st_size, "decoded_bytes": len(decoded), "sha256": checksum})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

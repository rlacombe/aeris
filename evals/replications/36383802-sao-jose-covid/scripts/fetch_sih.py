#!/usr/bin/env python3
"""Retrieve the official SIH/SUS RD files needed for PMID 36383802."""

from __future__ import annotations

import ftplib
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "sih"
HOST = "ftp.datasus.gov.br"
DIRECTORY = "/dissemin/publicos/SIHSUS/200801_/Dados"
MONTHS = [
    "2004", "2005", "2006", "2007", "2008", "2009", "2010", "2011", "2012",
    "2101", "2102", "2103", "2104",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def retrieve(ftp: ftplib.FTP, remote: str, destination: Path) -> None:
    partial = destination.with_suffix(".partial")
    if partial.exists():
        partial.unlink()
    with partial.open("wb") as handle:
        ftp.retrbinary(f"RETR {remote}", handle.write, blocksize=1024 * 1024)
    if partial.stat().st_size < 1024:
        raise RuntimeError(f"{remote} was implausibly small")
    partial.replace(destination)


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for suffix in MONTHS:
        remote = f"RDSP{suffix}.dbc"
        destination = RAW / remote
        if destination.exists() and destination.stat().st_size >= 1024:
            records.append({"file": remote, "status": "existing", "bytes": destination.stat().st_size, "sha256": sha256(destination)})
            continue
        errors: list[str] = []
        for attempt in range(1, 4):
            try:
                with ftplib.FTP(HOST, timeout=180) as ftp:
                    ftp.login()
                    ftp.cwd(DIRECTORY)
                    retrieve(ftp, remote, destination)
                records.append({"file": remote, "status": "downloaded", "attempt": attempt, "bytes": destination.stat().st_size, "sha256": sha256(destination)})
                break
            except (OSError, EOFError, ftplib.all_errors) as exc:
                errors.append(str(exc))
                time.sleep(attempt * 5)
        else:
            records.append({"file": remote, "status": "failed", "errors": errors})
    manifest = {
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": HOST,
        "directory": DIRECTORY,
        "records": records,
        "complete": all(record["status"] in {"existing", "downloaded"} for record in records),
    }
    (RAW.parent / "sih_download_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

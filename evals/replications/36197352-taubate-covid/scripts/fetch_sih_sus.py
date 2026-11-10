#!/usr/bin/env python3
"""Download the twelve public SIH/SUS RD files covering the study period."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "sih_sus"
BASE = "ftp://ftp.datasus.gov.br/dissemin/publicos/SIHSUS/200801_/Dados"
MONTHS = [(2020, month) for month in range(4, 13)] + [(2021, month) for month in range(1, 4)]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    files = []
    for year, month in MONTHS:
        token = f"{year % 100:02d}{month:02d}"
        name = f"RDSP{token}.dbc"
        target = RAW / name
        url = f"{BASE}/{name}"
        if not target.exists():
            partial = target.with_suffix(".partial")
            try:
                partial.unlink(missing_ok=True)
                # DATASUS's public FTP server supports curl's passive transfer
                # path reliably; urllib's FTP handler can stall after a file.
                process = subprocess.run(
                    ["curl", "--fail", "--silent", "--show-error", "--disable-epsv", "--connect-timeout", "15", "--max-time", "30", "--retry", "10", "--retry-delay", "3", "--retry-all-errors", url, "-o", str(partial)],
                    check=False,
                    text=True,
                    capture_output=True,
                )
                if process.returncode:
                    raise RuntimeError(process.stderr.strip() or f"curl exited {process.returncode}")
                if partial.stat().st_size < 1024:
                    raise RuntimeError("Downloaded file is implausibly small")
                partial.replace(target)
                print(f"retrieved {name}", flush=True)
            except (OSError, RuntimeError) as exc:
                partial.unlink(missing_ok=True)
                files.append({"month": f"{year}-{month:02d}", "url": url, "status": "ERROR", "error": str(exc)})
                print(f"failed {name}: {exc}", flush=True)
                continue
        files.append({"month": f"{year}-{month:02d}", "url": url, "path": str(target), "status": "OK", "bytes": target.stat().st_size, "sha256": sha256(target)})
    record = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "files": files}
    (RAW / "download_manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))
    return 0 if all(item["status"] == "OK" for item in files) else 1


if __name__ == "__main__":
    raise SystemExit(main())

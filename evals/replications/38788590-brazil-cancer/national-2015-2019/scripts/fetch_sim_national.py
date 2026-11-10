#!/usr/bin/env python3
"""Download public resident-SIM files for every Brazilian state and study year."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import shutil
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "sim"
YEARS = range(2015, 2020)
UFS = ("AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO")
OFFICIAL = "https://ftp.datasus.gov.br/dissemin/publicos/SIM/CID10/DORES/DO{uf}{year}.dbc"
MIRROR = "https://datasus-ftp-mirror.nyc3.digitaloceanspaces.com/SIM/CID10/DORES/DO{uf}{year}.dbc"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def get(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "AERIS-reproduction/1.0"})
    with urllib.request.urlopen(request, timeout=180) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="*", type=int, default=list(YEARS))
    parser.add_argument("--ufs", nargs="*", default=list(UFS))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--workers", type=int, default=6, help="Bounded concurrent downloads.")
    args = parser.parse_args()
    selected_ufs = tuple(value.upper() for value in args.ufs)
    unknown = sorted(set(selected_ufs) - set(UFS))
    if unknown:
        raise ValueError(f"Unknown UF codes: {unknown}")
    RAW.mkdir(parents=True, exist_ok=True)
    def retrieve(uf: str, year: int) -> dict:
        name = f"DO{uf}{year}.dbc"
        output = RAW / name
        if output.exists() and not args.force:
            return {"file": name, "status": "existing", "bytes": output.stat().st_size, "sha256": digest(output)}
        errors = []
        # The unique partial path keeps concurrent state-year downloads isolated.
        partial = output.with_suffix(".partial")
        for label, template in (("official", OFFICIAL), ("mirror", MIRROR)):
            url = template.format(uf=uf, year=year)
            try:
                partial.unlink(missing_ok=True)
                get(url, partial)
                if partial.stat().st_size < 1024:
                    raise RuntimeError("download is implausibly small")
                partial.replace(output)
                return {"file": name, "status": "downloaded", "source": label, "url": url,
                        "bytes": output.stat().st_size, "sha256": digest(output)}
            except (OSError, urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as exc:
                errors.append({"source": label, "url": url, "error": str(exc)})
        return {"file": name, "status": "failed", "attempts": errors}

    tasks = [(uf, year) for year in args.years for uf in selected_ufs]
    records, failures = [], []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(retrieve, uf, year) for uf, year in tasks]
        for future in as_completed(futures):
            record = future.result()
            (failures if record["status"] == "failed" else records).append(record)
    manifest = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "years": args.years,
                "ufs": selected_ufs, "records": records, "failures": failures,
                "complete": not failures}
    (RAW / "download_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"downloaded_or_existing": len(records), "failures": len(failures), "manifest": str(RAW / "download_manifest.json")}, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

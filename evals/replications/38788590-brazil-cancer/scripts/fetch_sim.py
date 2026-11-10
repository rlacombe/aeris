#!/usr/bin/env python3
"""Download the public 2019 Sao Paulo SIM source file with provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "source_manifest.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "AERIS-reproduction/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        with destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    destination = RAW / "DOSP2019.dbc"
    log_path = RAW / "sim_download.json"
    if destination.exists() and not args.force:
        print(f"Using existing {destination}")
        return 0

    manifest = json.loads(MANIFEST.read_text())
    source = manifest["outcomes"]
    attempts: list[dict[str, str]] = []
    temporary = destination.with_suffix(".partial")
    for label, url in (("official", source["official_transfer_url"]), ("mirror", source["mirror_url"])):
        try:
            if temporary.exists():
                temporary.unlink()
            download(url, temporary)
            if temporary.stat().st_size < 1024:
                raise RuntimeError("downloaded file is implausibly small")
            temporary.replace(destination)
            record = {
                "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
                "source_label": label,
                "source_url": url,
                "bytes": destination.stat().st_size,
                "sha256": sha256(destination),
                "attempts": attempts,
            }
            log_path.write_text(json.dumps(record, indent=2) + "\n")
            print(json.dumps(record, indent=2))
            return 0
        except (OSError, urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as exc:
            attempts.append({"source_label": label, "source_url": url, "error": str(exc)})

    log_path.write_text(json.dumps({"attempts": attempts}, indent=2) + "\n")
    print(json.dumps({"error": "SIM download failed", "attempts": attempts}, indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

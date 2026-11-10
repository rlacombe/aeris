#!/usr/bin/env python3
"""Download the public monthly SIH/SUS RDSP files for the study period."""

from __future__ import annotations

import hashlib
import json
import shutil
import urllib.error
import urllib.request
import argparse
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "sih"
URL = "https://ftp.datasus.gov.br/dissemin/publicos/SIHSUS/200801_/Dados/RDSP{yy}{mm}.dbc"
MIRROR_URL = "https://datasus-ftp-mirror.nyc3.digitaloceanspaces.com/SIHSUS/200801_/Dados/RDSP{yy}{mm}.dbc"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefer-mirror", action="store_true", help="Use the documented public mirror first after an official-host timeout.")
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    files = []
    for year in range(2012, 2016):
        for month in range(1, 13):
            name = f"RDSP{year % 100:02d}{month:02d}.dbc"
            target = RAW / name
            url = URL.format(yy=f"{year % 100:02d}", mm=f"{month:02d}")
            mirror = MIRROR_URL.format(yy=f"{year % 100:02d}", mm=f"{month:02d}")
            source = "existing"
            if not target.exists():
                errors = []
                candidates = (("mirror", mirror), ("official", url)) if args.prefer_mirror else (("official", url), ("mirror", mirror))
                for source, candidate in candidates:
                    temporary = target.with_suffix(".partial")
                    request = urllib.request.Request(candidate, headers={"User-Agent": "AERIS-reproduction/1.0"})
                    try:
                        with urllib.request.urlopen(request, timeout=90) as response, temporary.open("wb") as handle:
                            shutil.copyfileobj(response, handle)
                        if temporary.stat().st_size < 1024:
                            raise RuntimeError("downloaded file is implausibly small")
                        temporary.replace(target)
                        break
                    except (OSError, urllib.error.URLError, urllib.error.HTTPError, RuntimeError) as exc:
                        temporary.unlink(missing_ok=True)
                        errors.append({"source": source, "url": candidate, "error": str(exc)})
                else:
                    raise RuntimeError(f"Unable to download {name}: {errors}")
            files.append({"file": name, "official_url": url, "mirror_url": mirror, "source": source, "bytes": target.stat().st_size, "sha256": sha256(target)})
            print(f"{name}: {files[-1]['bytes']} bytes")
    manifest = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat(), "official_source_template": URL, "mirror_source_template": MIRROR_URL, "files": files}
    (RAW / "download_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

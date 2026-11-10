"""Acquire public non-exposure inputs for PMID 33484722.

This script preserves the WHO country-day series used to construct the
COVID-19 outcomes.  It does not retrieve or use the authors' PM2.5 values.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


RUN_DIRECTORY = Path(__file__).resolve().parent
WHO_URL = "https://srhdpeuwpubsa.blob.core.windows.net/whdh/COVID/WHO-COVID-19-global-data.csv"


def main() -> int:
    target = RUN_DIRECTORY / "WHO-COVID-19-global-data.csv"
    with urlopen(WHO_URL) as response:
        target.write_bytes(response.read())
    payload = target.read_bytes()
    manifest = {
        "source_url": WHO_URL,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }
    (RUN_DIRECTORY / "input_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

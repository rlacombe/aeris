#!/usr/bin/env python3
"""Write checksums for all canonical inputs and outputs in this replication."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {".DS_Store", "run_manifest.json"}


def checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    files = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.name in EXCLUDE or ".vendor" in path.parts:
            continue
        files.append({"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": checksum(path)})
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "pmid": "36383802",
        "files": files,
        "result": "Bounded reconstruction with public SIVEP-Gripe outcome fallback; SIH/SUS transfer remains unresolved.",
    }
    (ROOT / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"n_files": len(files), "manifest": str(ROOT / "run_manifest.json")}, indent=2))


if __name__ == "__main__":
    main()

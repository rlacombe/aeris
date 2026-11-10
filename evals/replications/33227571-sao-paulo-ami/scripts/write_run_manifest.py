#!/usr/bin/env python3
"""Write SHA-256 inventory for the completed reconstruction."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> int:
    paths = [path for path in ROOT.rglob("*") if path.is_file() and ".vendor" not in path.parts and path.name != "run_manifest.json"]
    records = [{"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": digest(path)} for path in sorted(paths)]
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "files": records}
    (ROOT / "run_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"files": len(records)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

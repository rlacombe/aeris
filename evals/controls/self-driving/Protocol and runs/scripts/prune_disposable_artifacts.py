#!/usr/bin/env python3
"""Remove reproducible environment caches while preserving scientific artifacts."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


DISPOSABLE_DIRECTORY_NAMES = {
    ".cache", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv",
    "__pycache__", "node_modules", "pip-cache", "venv",
}


def directory_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def prune(root: Path) -> list[dict[str, object]]:
    root = root.resolve()
    candidates = sorted(
        (path for path in root.rglob("*") if path.is_dir()
         and path.name in DISPOSABLE_DIRECTORY_NAMES),
        key=lambda path: len(path.parts),
    )
    removed = []
    for path in candidates:
        if not path.exists() or any(parent.name in DISPOSABLE_DIRECTORY_NAMES for parent in path.parents):
            continue
        path.resolve().relative_to(root)
        size = directory_bytes(path)
        relative = str(path.relative_to(root))
        shutil.rmtree(path)
        removed.append({"path": relative, "bytes": size, "reason": "reproducible environment cache"})
    return removed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    root = args.run_directory.resolve()
    report = {"schema_version": 1, "removed": prune(root)}
    report["bytes_removed"] = sum(item["bytes"] for item in report["removed"])
    (root / "disposable_artifact_pruning.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

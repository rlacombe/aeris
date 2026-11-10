#!/usr/bin/env python3
"""Fail when the container cannot resolve a host that the launch host can resolve."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("host", type=Path)
    parser.add_argument("container", type=Path)
    args = parser.parse_args()
    host = {row["host"]: row for row in json.loads(args.host.read_text())["probes"]}
    container = {row["host"]: row for row in json.loads(args.container.read_text())["probes"]}
    mismatches = [name for name, row in host.items() if row["dns"] and not container.get(name, {}).get("dns")]
    print(json.dumps({"valid": not mismatches, "container_dns_failures": mismatches}, indent=2))
    return 0 if not mismatches else 2


if __name__ == "__main__":
    raise SystemExit(main())

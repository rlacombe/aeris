#!/usr/bin/env python3
"""Check DNS and HTTP reachability without treating access controls as absence."""

from __future__ import annotations

import argparse
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


STANDARD_URLS = [
    "https://api.openaq.org/",
    "https://openaq-data-archive.s3.amazonaws.com/",
    "https://eutils.ncbi.nlm.nih.gov/",
    "https://api.crossref.org/",
    "https://www.geoboundaries.org/",
]


def probe(url: str, attempts: int = 3) -> dict:
    host = urllib.parse.urlparse(url).hostname
    row = {"url": url, "host": host, "dns": False, "http_reachable": False, "status": None, "error": None}
    for attempt in range(1, attempts + 1):
        try:
            socket.getaddrinfo(host, 443)
            row["dns"] = True
            break
        except OSError as exc:
            row["error"] = f"dns after {attempt} attempt(s): {exc}"
            if attempt < attempts:
                time.sleep(attempt)
    if not row["dns"]:
        return row
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "AERIS-evaluation-preflight/1.0"})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                row["status"] = response.status
                row["http_reachable"] = True
            break
        except urllib.error.HTTPError as exc:
            row["status"] = exc.code
            row["http_reachable"] = True
            break
        except Exception as exc:
            row["error"] = f"http after {attempt} attempt(s): {exc}"
            if attempt < attempts:
                time.sleep(attempt)
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brief", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    brief = json.loads(args.brief.read_text())
    urls = list(STANDARD_URLS)
    urls.extend(row["url"] for row in brief["public_sources"] if row.get("url"))
    rows = [probe(url) for url in dict.fromkeys(urls)]
    report = {"schema_version": 1, "probes": rows, "dns_complete": all(row["dns"] for row in rows)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["dns_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

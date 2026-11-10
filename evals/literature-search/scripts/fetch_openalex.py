#!/usr/bin/env python3
"""Fetch every result from a frozen OpenAlex query with cursor pagination."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


BASE = "https://api.openalex.org/works"


def fetch(url: str) -> dict:
    with urlopen(url, timeout=60) as response:
        return json.loads(response.read())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--per-page", type=int, default=200)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    common = {
        "search": args.query,
        "filter": f"from_publication_date:{args.start},to_publication_date:{args.end}",
        "per-page": str(args.per_page),
    }
    # OpenAlex emits `next_cursor` only when cursor mode is requested initially.
    first_url = f"{BASE}?{urlencode({**common, 'cursor': '*'})}"
    first = fetch(first_url)
    total = int(first["meta"]["count"])
    retrieved_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    manifest = {
        "label": args.label,
        "database": "openalex",
        "retrieved_at_utc": retrieved_at,
        "query": args.query,
        "start": args.start,
        "end": args.end,
        "query_url": first_url,
        "count": total,
        "per_page": args.per_page,
        "pagination": "cursor",
        "note": "Raw JSON pages contain all returned identifiers and metadata.",
    }
    (args.out / f"{args.label}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    page = first
    cursor = "*"
    seen = 0
    page_number = 0
    works: list[dict] = []
    while True:
        page_path = args.out / f"{args.label}.page.{page_number:05d}.json"
        page_path.write_text(json.dumps(page, indent=2) + "\n")
        results = page.get("results", [])
        works.extend(results)
        seen += len(results)
        cursor = page.get("meta", {}).get("next_cursor")
        if not results or not cursor:
            break
        url = f"{BASE}?{urlencode({**common, 'cursor': cursor})}"
        page = fetch(url)
        page_number += 1
        time.sleep(0.12)

    if seen != total:
        raise RuntimeError(f"Expected {total} works, received {seen}")
    fields = ["openalex_id", "doi", "pmid", "title", "publication_date", "type", "landing_page"]
    lines = [",".join(fields)]
    for work in works:
        ids = work.get("ids") or {}
        values = [
            work.get("id", ""), ids.get("doi", ""), ids.get("pmid", ""),
            work.get("title", ""), work.get("publication_date", ""),
            work.get("type", ""), work.get("doi") or work.get("id", ""),
        ]
        lines.append(",".join('"' + str(value).replace('"', '""') + '"' for value in values))
    (args.out / f"{args.label}.works.csv").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

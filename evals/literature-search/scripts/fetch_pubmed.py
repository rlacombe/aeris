#!/usr/bin/env python3
"""Fetch and preserve a PubMed search result for the AERIS evidence screen.

The output is deliberately a retrieval and screening-input artifact. It does
not infer that any citation is eligible for the replication benchmark.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def request(endpoint: str, params: dict[str, str]) -> bytes:
    url = f"{BASE}/{endpoint}?{urllib.parse.urlencode(params)}"
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AERIS-literature-audit/1.0"})
            with urllib.request.urlopen(req, timeout=90) as response:
                return response.read()
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def text(node: ET.Element | None, xpath: str) -> str:
    found = node.find(xpath) if node is not None else None
    return "".join(found.itertext()).strip() if found is not None else ""


def article_row(article: ET.Element) -> dict[str, str]:
    medline = article.find("MedlineCitation")
    article_node = medline.find("Article") if medline is not None else None
    journal = article_node.find("Journal") if article_node is not None else None
    pubdate = text(journal, "JournalIssue/PubDate/Year") or text(journal, "JournalIssue/PubDate/MedlineDate")
    ids = {item.attrib.get("IdType", ""): "".join(item.itertext()).strip()
           for item in article.findall("PubmedData/ArticleIdList/ArticleId")}
    return {
        "pmid": text(medline, "PMID"),
        "title": text(article_node, "ArticleTitle"),
        "journal": text(journal, "Title"),
        "publication_date": pubdate,
        "doi": ids.get("doi", ""),
        "pmc_id": ids.get("pmc", ""),
        "abstract": " ".join("".join(x.itertext()).strip() for x in article_node.findall("Abstract/AbstractText")) if article_node is not None else "",
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{text(medline, 'PMID')}/",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--ids-only", action="store_true", help="Preserve every PMID without downloading article XML.")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    retrieved_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    search_params = {"db": "pubmed", "term": args.query, "usehistory": "y", "retmax": "0", "retmode": "xml"}
    raw_search = request("esearch.fcgi", search_params)
    (args.out / f"{args.label}.esearch.xml").write_bytes(raw_search)
    root = ET.fromstring(raw_search)
    result = root if root.tag == "eSearchResult" else root.find("eSearchResult")
    assert result is not None
    count = int(text(result, "Count"))
    webenv, query_key = text(result, "WebEnv"), text(result, "QueryKey")
    manifest = {
        "label": args.label,
        "retrieved_at_utc": retrieved_at,
        "database": "pubmed",
        "query": args.query,
        "query_url": f"https://pubmed.ncbi.nlm.nih.gov/?term={urllib.parse.quote_plus(args.query)}",
        "api_search_parameters": search_params,
        "count": count,
        "page_size": args.batch_size,
        "pages": (count + args.batch_size - 1) // args.batch_size,
        "webenv": webenv,
        "query_key": query_key,
        "note": "WebEnv is an expiring NCBI history token; raw XML and the persistent PubMed query URL are preserved instead.",
    }
    (args.out / f"{args.label}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    rows: list[dict[str, str]] = []
    for start in range(0, count, args.batch_size):
        if args.ids_only:
            batch = request("esearch.fcgi", {
                # Re-send the query for each page. PubMed history pagination
                # can otherwise return a history-set rather than this search.
                "db": "pubmed", "term": args.query,
                "retstart": str(start), "retmax": str(args.batch_size), "retmode": "xml",
            })
            (args.out / f"{args.label}.esearch.{start:05d}.xml").write_bytes(batch)
            batch_root = ET.fromstring(batch)
            rows.extend({"pmid": node.text or "", "title": "", "journal": "", "publication_date": "", "doi": "", "pmc_id": "", "abstract": "", "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{node.text}/"} for node in batch_root.findall("IdList/Id"))
        else:
            batch = request("efetch.fcgi", {
                "db": "pubmed", "query_key": query_key, "WebEnv": webenv,
                "retstart": str(start), "retmax": str(args.batch_size), "retmode": "xml",
            })
            (args.out / f"{args.label}.efetch.{start:05d}.xml").write_bytes(batch)
            batch_root = ET.fromstring(batch)
            rows.extend(article_row(article) for article in batch_root.findall("PubmedArticle"))
        time.sleep(0.34)

    if len(rows) != count:
        raise RuntimeError(f"Expected {count} citations, received {len(rows)}")
    citation_fields = list(rows[0]) if rows else ["pmid"]
    with (args.out / f"{args.label}.citations.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=citation_fields)
        writer.writeheader()
        writer.writerows(rows)
    with (args.out / f"{args.label}.pmids.txt").open("w") as handle:
        handle.write("\n".join(row["pmid"] for row in rows) + "\n")

    ledger_fields = [
        "pmid", "citation", "title_abstract_screen", "full_text_screen",
        "human_health_study_evidence", "ambient_pollutant_evidence",
        "publication_date_evidence", "observation_start_year",
        "observation_start_evidence_url", "outcome_covariate_data_public",
        "outcome_covariate_data_url", "area_location_time_public",
        "area_location_time_evidence_url", "author_exposure_public_background",
        "author_exposure_evidence_url", "historical_openaq_retrievable",
        "openaq_evidence_url", "eligibility_decision", "exclusion_reason",
        "screener", "screened_at_utc", "notes",
    ]
    with (args.out / f"{args.label}.screening-ledger.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ledger_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "pmid": row["pmid"],
                "citation": f"{row['title']} ({row['journal']}; {row['publication_date']})" if row["title"] else "not fetched; use PubMed URL",
                "title_abstract_screen": "unreviewed",
                "full_text_screen": "unreviewed",
                "human_health_study_evidence": "unverified",
                "ambient_pollutant_evidence": "unverified",
                "publication_date_evidence": row["publication_date"],
                "outcome_covariate_data_public": "unverified",
                "area_location_time_public": "unverified",
                "author_exposure_public_background": "unverified",
                "historical_openaq_retrievable": "unverified",
                "eligibility_decision": "pending",
            })


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create an auditable, conservative rapid-screening ledger for Phase 1 v4."""

import csv
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "phase1-v4" / "raw"
MASTER = ROOT / "phase1-v4" / "phase1_v4_pubmed_openalex_master.csv"
OUT = ROOT / "phase1-v4" / "phase1_v4_rapid_screening_ledger.csv"
SUMMARY = ROOT / "phase1-v4" / "phase1_v4_rapid_screening_summary.txt"

POLLUTANT = (
    "air pollution", "air quality", "pm2.5", "pm 2.5", "pm10", "pm 10",
    "particulate matter", "nitrogen dioxide", "no2", "nox", "ozone", "o3",
    "sulfur dioxide", "so2", "carbon monoxide", "co exposure", "wildfire smoke",
)
HEALTH = (
    "health", "mortality", "morbidity", "hospital", "admission", "emergency",
    "asthma", "respiratory", "cardiovascular", "myocard", "stroke", "birth",
    "pregnan", "infant", "child", "pediatric", "mental", "depression", "anxiety",
    "disease", "cancer", "diabetes", "death", "patient", "clinical", "incidence",
    "epidemiolog", "healthcare",
)
REVIEWS = (
    "systematic review", "scoping review", "narrative review", "umbrella review",
    "meta-analysis", "meta analysis", "bibliometric",
)
NON_PRIMARY = (
    "study protocol", "trial protocol", "protocol for", "editorial", "commentary",
    "perspective", "letter to the editor",
)
NON_HUMAN = (
    "mouse", "mice", "rat", "rats", "murine", "zebrafish", "drosophila",
    "in vitro", "cell culture", "cellular", "toxicology study",
)
INDOOR_OR_PRIVATE = (
    "indoor air", "household air pollution", "cooking smoke", "biomass cook",
    "occupational exposure", "workplace exposure", "secondhand smoke", "tobacco smoke",
    "electronic cigarette", "e-cigarette",
)
AMBIENT = ("ambient", "outdoor", "background", "wildfire smoke", "air pollution", "air quality")
METHOD_ONLY = (
    "monitoring", "sensor", "calibration", "measurement technique", "instrument",
    "detection", "forecasting", "prediction", "air quality model", "source apportionment",
    "chemical characterization", "emission inventory", "emissions", "concentration trend",
)


def contains(text, terms):
    return any(term in text for term in terms)


def pubmed_abstracts():
    abstracts = {}
    with (RAW / "v4_pubmed_deduplicated.citations.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            abstracts[row["pmid"]] = row.get("abstract", "")
    return abstracts


def decide(title, abstract):
    text = f"{title} {abstract}".lower()
    has_pollutant = contains(text, POLLUTANT)
    has_health = contains(text, HEALTH)

    if contains(text, REVIEWS):
        return "exclude", "review_or_evidence_synthesis", "Title or abstract identifies a review, meta-analysis, or bibliometric synthesis."
    if contains(text, NON_PRIMARY):
        return "exclude", "protocol_commentary_or_editorial", "Title or abstract identifies a protocol, commentary, editorial, perspective, or letter."
    if contains(text, NON_HUMAN) and not has_health:
        return "exclude", "non_human_or_laboratory_only", "Title or abstract identifies animal, in-vitro, or laboratory work without a human health analysis."
    if contains(text, INDOOR_OR_PRIVATE) and not contains(text, AMBIENT):
        return "exclude", "not_outdoor_ambient_exposure", "Title or abstract is limited to indoor, household, occupational, or tobacco-related exposure."
    if not has_pollutant:
        return "uncertain", "", "Available metadata does not clearly identify an eligible pollutant; retain for manual review."
    if contains(text, METHOD_ONLY) and not has_health:
        return "exclude", "no_human_health_outcome", "Title or abstract concerns emissions, monitoring, or exposure methods without a human health outcome."
    if not has_health:
        return "uncertain", "", "Available metadata does not clearly identify a human health outcome; retain for manual review."
    if not abstract:
        return "uncertain", "", "OpenAlex-only metadata lacks an abstract; retain for manual review."
    return "retain", "", "Title and abstract indicate an outdoor ambient air-pollution and human-health study."


def main():
    abstracts = pubmed_abstracts()
    with MASTER.open(newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))

    fields = [
        "master_id", "title", "publication_date", "doi", "pubmed_pmid", "openalex_id",
        "sources", "openalex_query_labels", "cross_source_match_method", "pubmed_url",
        "openalex_landing_page", "abstract_available", "screening_stage", "screening_decision",
        "primary_exclusion_code", "evidence_note",
    ]
    decisions = Counter()
    exclusions = Counter()
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            abstract = abstracts.get(record["pubmed_pmid"], "")
            decision, code, note = decide(record["title"], abstract)
            decisions[decision] += 1
            if code:
                exclusions[code] += 1
            writer.writerow({
                **record,
                "abstract_available": "yes" if abstract else "no",
                "screening_stage": "rapid_title_abstract_metadata",
                "screening_decision": decision,
                "primary_exclusion_code": code,
                "evidence_note": note,
            })

    lines = [
        "# Phase 1 v4 Rapid Title/Abstract/Metadata Screen",
        "",
        f"Input deduplicated reports: {len(records)}",
        f"Retain: {decisions['retain']}",
        f"Exclude: {decisions['exclude']}",
        f"Uncertain: {decisions['uncertain']}",
        "",
        "## Clear exclusion reasons",
    ]
    lines.extend(f"- {code}: {count}" for code, count in sorted(exclusions.items()))
    lines.extend([
        "",
        "This is a conservative automated triage. It does not decide study-observation dates, open-access status, or data-route eligibility. Those are later Phase 1 gates.",
    ])
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

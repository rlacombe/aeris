#!/usr/bin/env python3
"""Validate article inputs and neutral study briefs before a run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TARGET = {
    "outcome", "population", "period", "geography", "pollutants",
    "exposure", "analysis", "covariates", "comparison_contrasts",
}
EXCLUDED = {
    "published_effect", "prior_aeris_effect", "prior_reanalysis_code",
    "prior_exposure_values",
}


def digest_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(str(item.relative_to(path)).encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return digest.hexdigest()


def validate(study_id: str, root: Path = ROOT) -> dict:
    bundle = root / "studies" / study_id
    brief_path = root / "briefs" / f"{study_id}.json"
    errors: list[str] = []
    if not bundle.is_dir():
        return {"study_id": study_id, "valid": False, "errors": ["missing study bundle"]}
    if not brief_path.is_file():
        return {"study_id": study_id, "valid": False, "errors": ["missing neutral study brief"]}

    manifest = json.loads((bundle / "materials_manifest.json").read_text())
    brief = json.loads(brief_path.read_text())
    text = (bundle / "article.txt").read_text(encoding="utf-8", errors="replace")
    files = manifest.get("files", [])
    full_text = any(row.get("role") == "article_source" for row in files)
    input_mode = manifest.get("input_mode")
    if input_mode is None:
        input_mode = (
            "retrieval_required"
            if manifest.get("full_text_status") == "not_in_public_full_text_archive"
            else "complete_article" if full_text else None
        )
    word_count = len(text.split())
    if input_mode == "complete_article":
        if manifest.get("full_text_status") == "not_in_public_full_text_archive" or not full_text:
            errors.append("complete-article bundle contains only a citation record")
        if word_count < 1500:
            errors.append(f"article text is too short for methods extraction ({word_count} words)")
        if not re.search(r"\b(method|methods|methodology)\b", text, re.IGNORECASE):
            errors.append("article text has no identifiable methods section")
    elif input_mode == "retrieval_required":
        if manifest.get("full_text_status") != "not_in_public_full_text_archive":
            errors.append("retrieval-required bundle has inconsistent full-text status")
        if not manifest.get("agent_instruction"):
            errors.append("retrieval-required bundle lacks an agent instruction")
        if not any(row.get("role") == "pubmed_record" for row in files):
            errors.append("retrieval-required bundle lacks an official citation record")
        if not re.search(r"\b10\.\d{4,9}/\S+", text):
            errors.append("retrieval-required citation record lacks a DOI")
    else:
        errors.append("materials manifest has no valid input_mode")
    if brief.get("schema_version") != 1 or brief.get("study_id") != study_id:
        errors.append("study brief identity or schema version is invalid")
    if set(brief.get("target", {})) != REQUIRED_TARGET:
        errors.append("study brief target fields are incomplete or unexpected")
    if not brief.get("public_sources") or not brief.get("evidence"):
        errors.append("study brief lacks public-source or evidence records")
    if set(brief.get("excluded_information", [])) != EXCLUDED:
        errors.append("study brief does not declare all prohibited answer fields")
    serialized = brief_path.read_text().casefold()
    for forbidden in ("published_ratio", "aeris_ratio", "prior estimate", "confidence interval"):
        if forbidden in serialized:
            errors.append(f"study brief contains prohibited answer-like field: {forbidden}")

    return {
        "study_id": study_id,
        "valid": not errors,
        "errors": errors,
        "article_words": word_count,
        "input_mode": input_mode,
        "supplement_files": len(list((bundle / "supplements").glob("*"))),
        "bundle_sha256": digest_tree(bundle),
        "brief_sha256": hashlib.sha256(brief_path.read_bytes()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("study_id", nargs="?")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.all:
        studies = [path.name for path in sorted((ROOT / "studies").iterdir()) if path.is_dir()]
    elif args.study_id:
        studies = [args.study_id]
    else:
        parser.error("provide study_id or --all")
    report = {"schema_version": 1, "studies": [validate(study) for study in studies]}
    report["valid"] = all(row["valid"] for row in report["studies"])
    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(payload)
    print(payload, end="")
    return 0 if report["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

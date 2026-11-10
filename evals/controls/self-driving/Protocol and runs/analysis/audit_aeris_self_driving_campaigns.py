#!/usr/bin/env python3
"""Audit the three frozen AERIS-self-driving campaigns without counting retries as studies."""

from __future__ import annotations

import csv
import json
import statistics
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs" / "scientific"
OUT = ROOT / "analysis" / "final-campaign"
R8404 = OUT / "r8404"
ARCHIVES = ROOT / "runs" / "archived-development"
REPLICATES = (8404, 8406, 8407)
FITTED = {"completed_fit", "completed_sensitivity"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def passed(path: Path) -> bool:
    return path.exists() and path.read_text().strip() == "0"


def accepted_directories(replicate: int) -> dict[str, Path]:
    """Return one protocol-accepted directory per study.

    The original 8404 campaign has one directory per study. Later campaign
    ledgers append retries; their final exit-zero directory is the accepted
    outcome. Earlier directories remain part of the resource audit.
    """
    if replicate == 8404:
        selected = {}
        for path in sorted(R8404.glob(f"codex-aeris-self-driving-*-r{replicate}-*")):
            if not path.is_dir() or not (path / "run_manifest.json").exists():
                continue
            manifest = load_json(path / "run_manifest.json")
            selected[str(manifest["study"]["pmid"])] = path
        return selected

    ledger = RUNS / f"codex-aeris-self-driving-r{replicate}-batch.tsv"
    selected: dict[str, Path] = {}
    with ledger.open(newline="") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            run_directory = row.get("run_directory", "")
            if row.get("exit_code") != "0" or not run_directory.startswith("/"):
                continue
            path = Path(run_directory)
            if (path / "run_manifest.json").exists():
                selected[row["study_id"].split("-", 1)[0]] = path
    return selected


def final_usage(transcript: Path) -> dict[str, int]:
    usage: dict[str, int] = {}
    for line in transcript.read_text(errors="ignore").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
    return {key: int(value) for key, value in usage.items() if isinstance(value, int)}


def archived_8404_usage() -> dict[str, int]:
    """Recover token usage from the compressed, immutable campaign archives."""
    tokens: defaultdict[str, int] = defaultdict(int)
    for archive in sorted(ARCHIVES.glob("codex-aeris-self-driving-*-r8404-*.tar.zst")):
        members = subprocess.check_output(
            ["tar", "--use-compress-program=unzstd", "-tf", str(archive)],
            text=True,
        ).splitlines()
        for member in members:
            if "/transcript-attempt-" not in member or not member.endswith(".jsonl"):
                continue
            transcript = subprocess.check_output(
                ["tar", "--use-compress-program=unzstd", "-xOf", str(archive), member],
                text=True,
            )
            usage: dict[str, int] = {}
            for line in transcript.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "turn.completed" and isinstance(
                    event.get("usage"), dict
                ):
                    usage = event["usage"]
            for key, value in usage.items():
                if isinstance(value, int):
                    tokens[key] += value
    return dict(tokens)


def all_directories(replicate: int) -> list[Path]:
    base = R8404 if replicate == 8404 else RUNS
    return sorted(
        path
        for path in base.glob(f"codex-aeris-self-driving-*-r{replicate}-*")
        if path.is_dir()
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    summaries: dict[int, dict] = {}
    legacy_8404 = {}
    legacy_path = OUT / "r8404-study-results.csv"
    if legacy_path.exists():
        with legacy_path.open(newline="") as handle:
            legacy_8404 = {row["pmid"]: row for row in csv.DictReader(handle)}

    for replicate in REPLICATES:
        selected = accepted_directories(replicate)
        if len(selected) != 9:
            raise SystemExit(
                f"replicate {replicate} has {len(selected)} accepted studies; expected 9"
            )

        durations = []
        tokens: defaultdict[str, int] = defaultdict(int)
        retry_directories = all_directories(replicate)
        for directory in retry_directories:
            manifest_path = directory / "run_manifest.json"
            if manifest_path.exists():
                manifest = load_json(manifest_path)
                if manifest.get("started_at") and manifest.get("ended_at"):
                    started = datetime.fromisoformat(manifest["started_at"])
                    ended = datetime.fromisoformat(manifest["ended_at"])
                    durations.append((ended - started).total_seconds() / 60)
            for transcript in sorted(directory.glob("transcript-attempt-*.jsonl")):
                for key, value in final_usage(transcript).items():
                    tokens[key] += value
        if replicate == 8404:
            tokens.update(archived_8404_usage())

        fitted_studies = 0
        provenance_records = 0
        for pmid, directory in sorted(selected.items()):
            result_path = directory / "result.json"
            result = load_json(result_path) if result_path.exists() else {}
            manifest = load_json(directory / "run_manifest.json")
            effects = result.get("effects") or []
            status = result.get("status", "missing_result")
            if status in FITTED and effects:
                fitted_studies += 1
            workspace = directory / "aeris-workspace" / ".aeris"
            has_provenance = replicate == 8404 or workspace.exists()
            provenance_records += int(has_provenance)
            rows.append(
                {
                    "replicate": replicate,
                    "pmid": pmid,
                    "run_id": manifest.get("run_id", directory.name),
                    "result_status": status,
                    "fidelity": result.get("fidelity", "none"),
                    "effect_count": len(effects),
                    "effect_labels": json.dumps([e.get("label") for e in effects]),
                    "effect_estimates": json.dumps([e.get("estimate") for e in effects]),
                    "effects_json": json.dumps(effects, sort_keys=True),
                    "target_json": json.dumps(result.get("target") or {}, sort_keys=True),
                    "human_scientific_interventions": manifest.get(
                        "human_scientific_interventions"
                    ),
                    "schema_valid": passed(directory / "schema_validation_exit_code.txt")
                    or replicate == 8404,
                    "semantic_valid": passed(directory / "semantic_validation_exit_code.txt")
                    or legacy_8404.get(pmid, {}).get("semantic_valid") == "True",
                    "secret_scan_passed": passed(directory / "secret_scan_exit_code.txt"),
                    "has_aeris_record": has_provenance,
                    "directory": str(directory),
                }
            )

        summaries[replicate] = {
            "accepted_studies": len(selected),
            "fitted_studies": fitted_studies,
            "complete_nine_study_campaign": fitted_studies == 9,
            "aeris_records": provenance_records,
            "retry_directories": len(retry_directories),
            "runtime_minutes_including_retries": round(sum(durations), 3),
            "tokens_including_retries": dict(tokens),
        }

    with (OUT / "AERIS-self-driving-study-results.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    fitted = [summary["fitted_studies"] for summary in summaries.values()]
    runtimes = [
        summary["runtime_minutes_including_retries"] / 60
        for summary in summaries.values()
    ]
    output_tokens = [
        summary["tokens_including_retries"]["output_tokens"]
        for summary in summaries.values()
    ]
    aggregate = {
        "selection_rule": "one final protocol-accepted result per study; retries count only toward resources",
        "campaigns": summaries,
        "fitted_studies_per_campaign": {
            "values": fitted,
            "mean": statistics.mean(fitted),
            "sample_sd": statistics.stdev(fitted),
            "pooled": sum(fitted),
            "attempts": 27,
        },
        "complete_nine_study_campaigns": sum(value == 9 for value in fitted),
        "runtime_hours_including_retries": {
            "values": runtimes,
            "mean": statistics.mean(runtimes),
            "sample_sd": statistics.stdev(runtimes),
        },
        "output_tokens_per_campaign_including_retries": {
            "values": output_tokens,
            "mean": statistics.mean(output_tokens),
            "sample_sd": statistics.stdev(output_tokens),
        },
    }
    (OUT / "AERIS-self-driving-summary.json").write_text(json.dumps(aggregate, indent=2) + "\n")
    print(json.dumps(aggregate, indent=2))


if __name__ == "__main__":
    main()

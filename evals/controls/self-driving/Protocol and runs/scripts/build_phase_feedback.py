#!/usr/bin/env python3
"""Build a short, phase-specific continuation instruction."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


GUIDANCE = {
    "specify": "Finish reading the paper and supplements. Resolve the estimand, lock only its scientific invariants, then proceed to public-data recovery.",
    "recover": "Continue the saved recovery actions. Treat failed routes as route failures, inspect archives or underlying endpoints, and build a minimal valid outcome-exposure slice before scaling it.",
    "fit": "Use the recovered data to finish the panel and model. Verify joins, contrast units, effect transformation, uncertainty, and retained executable code.",
    "audit": "Audit fidelity, coverage, geography, transformations, and stronger public alternatives. Repair actionable weaknesses, record fidelity with AERIS, and write analysis_handoff.json.",
    "complete": "The scientific work is marked complete. Repair or create analysis_handoff.json from retained scientific artifacts; do not inspect host validators or restart retrieval.",
}


def latest_notebook(output: Path) -> dict:
    candidates = [
        output / "aeris-workspace" / ".aeris" / "research-notebook.json",
        output / ".aeris" / "research-notebook.json",
        output / "research_notebook.json",
    ]
    for path in candidates:
        if path.is_file():
            return json.loads(path.read_text())
    return {}


def build(output: Path, reason: str = "") -> str:
    notebook = latest_notebook(output)
    phase = notebook.get("phase", "specify")
    next_actions = notebook.get("next_actions") or []
    lines = [
        f"Resume the same run in the {phase} phase.",
        GUIDANCE.get(phase, GUIDANCE["specify"]),
        "Keep the locked scientific target and reuse retained downloads, code, and checkpoints.",
    ]
    if next_actions:
        lines.append("Execute the notebook's next actions: " + "; ".join(map(str, next_actions[:5])))
    if reason:
        lines.append("Host observation: " + reason.strip())
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--reason", default="")
    parser.add_argument("--write", type=Path)
    args = parser.parse_args()
    text = build(args.output, args.reason)
    if args.write:
        args.write.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Auditable decision log for analytical choices.

Every analytical decision made during a REPL session (pollutant selection,
confounder adjustment, model specification, data exclusions) is recorded
with its rationale, alternatives considered, and the data context that
informed it. This log can be exported for supplementary materials in
publications.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DECISION_CATEGORIES = [
    "pollutant_selection",
    "exposure_model",
    "confounder_adjustment",
    "statistical_model",
    "data_exclusion",
    "sensitivity_analysis",
    "study_design",
    "effect_modification",
    "other",
]


@dataclass
class Decision:
    """A single analytical decision with full audit trail."""

    category: str
    choice: str
    rationale: str
    alternatives: list[str] = field(default_factory=list)
    data_context: dict = field(default_factory=dict)
    model_used: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "category": self.category,
            "choice": self.choice,
            "rationale": self.rationale,
            "alternatives": self.alternatives,
            "data_context": self.data_context,
            "model_used": self.model_used,
        }


class DecisionLog:
    """Ordered log of all analytical decisions in a session."""

    def __init__(self):
        self.decisions: list[Decision] = []

    def record(self, decision: Decision) -> int:
        """Record a decision. Returns the decision index (1-based)."""
        self.decisions.append(decision)
        return len(self.decisions)

    def __len__(self) -> int:
        return len(self.decisions)

    def to_markdown(self) -> str:
        """Export the full decision log as publication-ready markdown."""
        if not self.decisions:
            return "No decisions recorded yet."

        lines = [
            "# Analytical Decision Log",
            "",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "---",
            "",
        ]

        for i, d in enumerate(self.decisions, 1):
            lines.append(f"## Decision {i}: {d.category.replace('_', ' ').title()}")
            lines.append("")
            lines.append(f"**Timestamp:** {d.timestamp}")
            lines.append(f"**Choice:** {d.choice}")
            lines.append("")

            if d.alternatives:
                lines.append("**Alternatives considered:**")
                for alt in d.alternatives:
                    lines.append(f"- {alt}")
                lines.append("")

            lines.append("**Rationale:**")
            lines.append(d.rationale)
            lines.append("")

            if d.data_context:
                lines.append("**Data context at time of decision:**")
                for k, v in d.data_context.items():
                    lines.append(f"- {k}: {v}")
                lines.append("")

            if d.model_used:
                lines.append(f"**Model:** {d.model_used}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    def to_ascii(self) -> str:
        """Render a compact ASCII summary for terminal display."""
        if not self.decisions:
            return "No decisions recorded."

        lines = ["ANALYTICAL DECISION LOG", "=" * 40, ""]

        for i, d in enumerate(self.decisions, 1):
            ts = d.timestamp[:19].replace("T", " ")
            lines.append(f"  [{i}] {d.category.replace('_', ' ').title()}")
            lines.append(f"      Time: {ts}")
            lines.append(f"      Choice: {d.choice}")
            # Truncate rationale for terminal display
            rationale_preview = d.rationale[:120]
            if len(d.rationale) > 120:
                rationale_preview += "..."
            lines.append(f"      Rationale: {rationale_preview}")
            lines.append("")

        return "\n".join(lines)

    def save_markdown(self, path: str | Path) -> None:
        Path(path).write_text(self.to_markdown())

    def save_json(self, path: str | Path) -> None:
        data = [d.to_dict() for d in self.decisions]
        Path(path).write_text(json.dumps(data, indent=2))

    def to_dict_list(self) -> list[dict]:
        return [d.to_dict() for d in self.decisions]

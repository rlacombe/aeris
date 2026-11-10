"""
Causal DAG data structures and rendering.

Provides a structured representation of causal directed acyclic graphs (DAGs)
for epidemiological analysis. Supports export to Graphviz DOT, Mermaid, and
ASCII formats for publication and interactive use.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

VALID_ROLES = frozenset(
    {"exposure", "outcome", "confounder", "mediator", "collider", "effect_modifier"}
)


@dataclass
class DAGNode:
    """A variable in the causal DAG."""

    name: str
    role: str  # exposure, outcome, confounder, mediator, collider, effect_modifier
    description: str = ""

    def __post_init__(self):
        if self.role not in VALID_ROLES:
            raise ValueError(f"Invalid role '{self.role}'. Must be one of: {VALID_ROLES}")


@dataclass
class DAGEdge:
    """A directed edge in the causal DAG."""

    source: str
    target: str
    description: str = ""


class CausalDAG:
    """
    A causal directed acyclic graph for epidemiological analysis.

    Represents variables (nodes) and their causal relationships (edges),
    with support for identifying confounders, mediators, colliders, and
    computing adjustment sets.
    """

    def __init__(
        self,
        research_question: str,
        nodes: list[DAGNode],
        edges: list[DAGEdge],
        reasoning: str = "",
        adjustment_recommendation: str = "",
    ):
        self.research_question = research_question
        self.nodes: dict[str, DAGNode] = {n.name: n for n in nodes}
        self.edges = edges
        self.reasoning = reasoning
        self.adjustment_recommendation = adjustment_recommendation

    @property
    def exposure(self) -> str | None:
        return next((n for n, node in self.nodes.items() if node.role == "exposure"), None)

    @property
    def outcome(self) -> str | None:
        return next((n for n, node in self.nodes.items() if node.role == "outcome"), None)

    @property
    def confounders(self) -> list[str]:
        return [n for n, node in self.nodes.items() if node.role == "confounder"]

    @property
    def mediators(self) -> list[str]:
        return [n for n, node in self.nodes.items() if node.role == "mediator"]

    @property
    def colliders(self) -> list[str]:
        return [n for n, node in self.nodes.items() if node.role == "collider"]

    @property
    def effect_modifiers(self) -> list[str]:
        return [n for n, node in self.nodes.items() if node.role == "effect_modifier"]

    def adjustment_set(self) -> list[str]:
        """Minimal sufficient adjustment set (simplified backdoor criterion).

        Returns confounders — variables that are common causes of exposure and
        outcome. Does NOT include mediators (would block the causal path) or
        colliders (would induce spurious associations).
        """
        return self.confounders

    def to_dot(self) -> str:
        """Export as Graphviz DOT format for publication-quality figures."""
        lines = [
            "digraph DAG {",
            "  rankdir=LR;",
            '  node [shape=box, fontname="Helvetica", fontsize=11];',
            '  edge [fontname="Helvetica", fontsize=9];',
            "",
        ]

        role_styles = {
            "exposure": 'style=filled, fillcolor="#4CAF50", fontcolor=white',
            "outcome": 'style=filled, fillcolor="#F44336", fontcolor=white',
            "confounder": 'style=filled, fillcolor="#FFC107", fontcolor=black',
            "mediator": 'style=filled, fillcolor="#2196F3", fontcolor=white',
            "collider": 'style=filled, fillcolor="#9C27B0", fontcolor=white',
            "effect_modifier": 'style=filled, fillcolor="#FF9800", fontcolor=black',
        }

        for name, node in self.nodes.items():
            style = role_styles.get(node.role, "")
            safe_name = name.replace('"', '\\"')
            safe_role = node.role.replace("_", " ")
            label = f"{safe_name}\\n({safe_role})"
            lines.append(f'  "{safe_name}" [{style}, label="{label}"];')

        lines.append("")

        for edge in self.edges:
            src = edge.source.replace('"', '\\"')
            tgt = edge.target.replace('"', '\\"')
            label_attr = ""
            if edge.description:
                safe_desc = edge.description.replace('"', '\\"')
                label_attr = f' [label="{safe_desc}"]'
            lines.append(f'  "{src}" -> "{tgt}"{label_attr};')

        lines.append("}")
        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """Export as Mermaid diagram for markdown/web rendering."""
        lines = ["graph LR"]

        def safe_id(name: str) -> str:
            return name.replace(" ", "_").replace("-", "_")

        for name, node in self.nodes.items():
            sid = safe_id(name)
            lines.append(f'  {sid}["{name} ({node.role})"]')

        lines.append("")

        for edge in self.edges:
            src = safe_id(edge.source)
            tgt = safe_id(edge.target)
            if edge.description:
                lines.append(f"  {src} -->|{edge.description}| {tgt}")
            else:
                lines.append(f"  {src} --> {tgt}")

        return "\n".join(lines)

    def to_ascii(self) -> str:
        """Render a readable ASCII representation of the DAG."""
        lines = []
        lines.append(f"Research Question: {self.research_question}")
        lines.append("")

        for role in [
            "exposure",
            "outcome",
            "confounder",
            "mediator",
            "collider",
            "effect_modifier",
        ]:
            role_nodes = [n for n, node in self.nodes.items() if node.role == role]
            if role_nodes:
                lines.append(f"  {role.upper().replace('_', ' ')}:")
                for n in role_nodes:
                    desc = f" - {self.nodes[n].description}" if self.nodes[n].description else ""
                    lines.append(f"    * {n}{desc}")
                lines.append("")

        lines.append("  EDGES:")
        for edge in self.edges:
            desc = f" ({edge.description})" if edge.description else ""
            lines.append(f"    {edge.source} -> {edge.target}{desc}")

        adj = self.adjustment_set()
        lines.append("")
        lines.append(f"  ADJUSTMENT SET: {', '.join(adj) if adj else 'none'}")

        if self.adjustment_recommendation:
            lines.append("")
            lines.append(f"  RECOMMENDATION: {self.adjustment_recommendation}")

        return "\n".join(lines)

    def save_dot(self, path: str | Path) -> None:
        """Write DOT file to disk."""
        Path(path).write_text(self.to_dot())

    def to_dict(self) -> dict:
        return {
            "research_question": self.research_question,
            "nodes": [
                {"name": n, "role": node.role, "description": node.description}
                for n, node in self.nodes.items()
            ],
            "edges": [
                {"source": e.source, "target": e.target, "description": e.description}
                for e in self.edges
            ],
            "reasoning": self.reasoning,
            "adjustment_recommendation": self.adjustment_recommendation,
        }

    def save_json(self, path: str | Path) -> None:
        """Write JSON representation to disk."""
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def from_dict(cls, data: dict) -> CausalDAG:
        nodes = [DAGNode(**n) for n in data["nodes"]]
        edges = [DAGEdge(**e) for e in data["edges"]]
        return cls(
            research_question=data.get("research_question", ""),
            nodes=nodes,
            edges=edges,
            reasoning=data.get("reasoning", ""),
            adjustment_recommendation=data.get("adjustment_recommendation", ""),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> CausalDAG:
        """Load a DAG from a JSON file."""
        data = json.loads(Path(path).read_text())
        return cls.from_dict(data)

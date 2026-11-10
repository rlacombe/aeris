"""Durable, study-scoped artifacts for agentic AERIS workflows."""

from __future__ import annotations

import hashlib
import json
import re
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "artifact"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class StudyWorkspace:
    """Store inputs, result tables, and immutable manifests under ``.aeris``."""

    def __init__(self, root: Path):
        self.root = root / ".aeris"
        self.artifacts_dir = self.root / "artifacts"
        self.runs_dir = self.root / "runs"
        self.manifest_path = self.root / "workspace.json"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        if not self.manifest_path.exists():
            self._write_json(
                self.manifest_path,
                {"workspace_id": self.workspace_id, "created_at": _utc_now(), "artifacts": {}},
            )

    @property
    def workspace_id(self) -> str:
        digest = hashlib.sha256(str(self.root.resolve()).encode()).hexdigest()[:12]
        return f"study_{digest}"

    def register_dataframe(
        self, name: str, frame: pd.DataFrame, *, kind: str, provenance: dict[str, Any] | None = None
    ) -> str:
        artifact_id = f"{_slug(kind)}_{_slug(name)}_{_utc_now().replace(':', '').replace('+', '')}"
        table_path = self.artifacts_dir / f"{artifact_id}.csv"
        manifest_path = self.artifacts_dir / f"{artifact_id}.json"
        self._write_dataframe(table_path, frame)
        manifest = {
            "artifact_id": artifact_id,
            "kind": kind,
            "created_at": _utc_now(),
            "path": str(table_path),
            "row_count": int(len(frame)),
            "columns": list(frame.columns),
            "sha256": _sha256(table_path),
            "provenance": provenance or {},
        }
        self._write_json(manifest_path, manifest)
        workspace = self._read_json(self.manifest_path)
        workspace["artifacts"][artifact_id] = str(manifest_path)
        self._write_json(self.manifest_path, workspace)
        return artifact_id

    def register_run(self, name: str, payload: dict[str, Any]) -> str:
        run_id = f"run_{_slug(name)}_{_utc_now().replace(':', '').replace('+', '')}"
        run_path = self.runs_dir / f"{run_id}.json"
        self._write_json(run_path, {"run_id": run_id, "created_at": _utc_now(), **payload})
        return run_id

    def register_json(
        self, name: str, payload: dict[str, Any], *, kind: str, provenance: dict[str, Any] | None = None
    ) -> str:
        """Store a structured study artifact and add it to the workspace index."""
        artifact_id = f"{_slug(kind)}_{_slug(name)}_{_utc_now().replace(':', '').replace('+', '')}"
        data_path = self.artifacts_dir / f"{artifact_id}.json"
        manifest_path = self.artifacts_dir / f"{artifact_id}.manifest.json"
        self._write_json(data_path, payload)
        manifest = {
            "artifact_id": artifact_id,
            "kind": kind,
            "created_at": _utc_now(),
            "path": str(data_path),
            "sha256": _sha256(data_path),
            "provenance": provenance or {},
        }
        self._write_json(manifest_path, manifest)
        workspace = self._read_json(self.manifest_path)
        workspace["artifacts"][artifact_id] = str(manifest_path)
        self._write_json(self.manifest_path, workspace)
        return artifact_id

    def list_artifacts(self) -> list[dict[str, Any]]:
        workspace = self._read_json(self.manifest_path)
        return [self._read_json(Path(path)) for path in workspace.get("artifacts", {}).values()]

    def artifact_manifest(self, artifact_id: str) -> dict[str, Any]:
        workspace = self._read_json(self.manifest_path)
        path = workspace.get("artifacts", {}).get(artifact_id)
        if path is None:
            raise KeyError(f"Unknown artifact: {artifact_id}")
        return self._read_json(Path(path))

    def read_artifact(self, artifact_id: str) -> pd.DataFrame:
        return pd.read_csv(self.artifact_manifest(artifact_id)["path"])

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        content = json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
        StudyWorkspace._atomic_write(path, content.encode("utf-8"))

    @staticmethod
    def _write_dataframe(path: Path, frame: pd.DataFrame) -> None:
        content = frame.to_csv(index=False).encode("utf-8")
        StudyWorkspace._atomic_write(path, content)

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

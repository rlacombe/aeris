"""
Session state for the AERIS agent.

Holds the loaded cohort, exposure results, decision log,
and workflow progress. Shared by all MCP-hosted research sessions.
"""

from __future__ import annotations

import hashlib
import contextlib
import functools
import json
import logging
import os
import tempfile
from pathlib import Path

import pandas as pd

from aeris.exposure.cache import ResponseCache
from aeris.exposure.config import ALLOWED_POLLUTANTS, Config
from aeris.exposure.validators import detect_mode

from .decision_log import Decision, DecisionLog
from .execution import ExecutionPolicy
from .workspace import StudyWorkspace

log = logging.getLogger(__name__)


@contextlib.contextmanager
def _checkpoint_lock(checkpoint: Path | None):
    """Hold a process lock while reading and updating one batch checkpoint."""
    if checkpoint is None:
        yield
        return

    import fcntl

    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    lock_path = checkpoint.with_suffix(checkpoint.suffix + ".lock")
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                f"Another process is already updating checkpoint {checkpoint}."
            ) from exc
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()}\n")
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _single_checkpoint_writer(method):
    """Serialize a checkpointed batch across processes."""
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        checkpoint_value = kwargs.get("checkpoint_path")
        checkpoint = Path(checkpoint_value).expanduser() if checkpoint_value else None
        with _checkpoint_lock(checkpoint):
            return method(self, *args, **kwargs)

    return wrapped


def _atomic_text(path: Path, value: str) -> None:
    """Replace a text artifact atomically without sharing a temporary filename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_dataframe(path: Path, frame: pd.DataFrame) -> None:
    """Replace a CSV artifact atomically without sharing a temporary filename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            frame.to_csv(handle, index=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class SessionState:
    """All mutable state for one AERIS session."""

    def __init__(self):
        self.execution_policy = ExecutionPolicy.from_env()
        self.cohort: pd.DataFrame | None = None
        self.mode: str | None = None
        self.config = Config.from_env()
        self.results: dict[str, pd.DataFrame] = {}
        self.batch_daily_results: dict[str, pd.DataFrame] = {}
        self.decision_log = DecisionLog()
        self.input_path: str | None = None
        self.working_directory: str | None = None
        self.workflow_step: int = 1
        self.estimator = None
        self.boundary = None
        self.cache: ResponseCache | None = None
        self.workspace: StudyWorkspace | None = None
        self.artifacts: dict[str, str] = {}
        self.runs: dict[str, str] = {}
        self.exposure_plans: dict[str, dict] = {}

    @property
    def is_loaded(self) -> bool:
        return self.cohort is not None

    def load_cohort(self, csv_path: str) -> dict:
        """Load a cohort CSV and auto-detect mode. Returns a summary dict."""
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {csv_path}")

        self.working_directory = str(path.parent)
        workspace_directory = Path(os.getenv("AERIS_WORKSPACE", path.parent))
        workspace_directory.mkdir(parents=True, exist_ok=True)
        self.workspace = StudyWorkspace(workspace_directory)
        self._restore_workspace_contract()
        self._ensure_cache(workspace_directory)
        self.mode = detect_mode(csv_path)
        self.cohort = pd.read_csv(path)
        self.input_path = csv_path

        self.results.clear()
        self.batch_daily_results.clear()
        self.artifacts.clear()
        self.runs.clear()
        self.exposure_plans.clear()

        dataset_id = self.workspace.register_dataframe(
            path.stem,
            self.cohort,
            kind="dataset",
            provenance={"source_path": str(path.resolve()), "mode": self.mode},
        )
        self.artifacts["cohort"] = dataset_id

        summary = self.build_cohort_summary()

        self.decision_log.record(
            Decision(
                category="other",
                choice=f"Loaded cohort from {path.name}",
                rationale=f"Auto-detected {self.mode} mode with {len(self.cohort)} participants.",
                data_context=summary,
            )
        )

        return summary

    def register_result_artifact(self, name: str, frame: pd.DataFrame, provenance: dict) -> str | None:
        """Persist an exposure table and its scientific lineage when a workspace exists."""
        if self.workspace is None:
            return None
        artifact_id = self.workspace.register_dataframe(name, frame, kind="exposure", provenance=provenance)
        self.artifacts[f"result:{name}"] = artifact_id
        return artifact_id

    def ensure_workspace(self) -> StudyWorkspace:
        """Create a durable workspace for boundary-only and autonomous studies."""
        if self.workspace is None:
            directory = Path(os.getenv("AERIS_WORKSPACE", self.working_directory or Path.cwd()))
            directory.mkdir(parents=True, exist_ok=True)
            self.working_directory = str(directory)
            self.workspace = StudyWorkspace(directory)
            self._restore_workspace_contract()
            self._ensure_cache(directory)
        return self.workspace

    def _restore_workspace_contract(self) -> None:
        """Restore the latest append-only contract in a self-driving workspace."""
        if (
            self.workspace is None
            or self.execution_policy.mode != "self-driving"
            or self.execution_policy.contract is not None
        ):
            return
        contracts = self.workspace.root / "contracts"
        amendments = sorted(contracts.glob("agent-contract-amendment-[0-9][0-9][0-9].json"))
        candidates = amendments[-1:] or [
            path for path in (
                contracts / "reanalysis-invariants.json",
                contracts / "agent-exposure-contract.json",
            )
            if path.is_file()
        ]
        if not candidates:
            return
        contract = self.execution_policy.restore_agent_contract(candidates[0])
        log.info(
            "Restored durable AERIS contract %s (%s).",
            contract.payload["contract_id"],
            contract.digest,
        )

    def register_run(self, name: str, payload: dict) -> str | None:
        if self.workspace is None:
            return None
        run_id = self.workspace.register_run(name, payload)
        self.runs[name] = run_id
        return run_id

    def record_study_design(self, design: dict) -> str:
        """Persist a researcher-approved design record for the loaded study."""
        if self.workspace is None:
            raise RuntimeError("Load a cohort before recording a study design.")
        artifact_id = self.workspace.register_json(
            "study-design",
            design,
            kind="study-design",
            provenance={"dataset_id": self.artifacts.get("cohort")},
        )
        self.artifacts["study_design"] = artifact_id
        return artifact_id

    def _ensure_cache(self, directory: Path) -> None:
        """Create one durable, study-scoped OpenAQ cache when needed."""
        target = directory / ".aeris_openaq_cache.sqlite"
        if self.cache is not None and Path(self.cache.db_path) == target:
            return
        if self.cache is not None:
            self.cache.close()
        self.cache = ResponseCache(db_path=str(target), ttl_hours=24 * 30)

    def run_estimation(
        self,
        pollutant: str | None = None,
        backend: str = "gmaps",
        country: str = "us",
        n_stations: int = 1,
        outlier_detection: bool = False,
        min_completeness: float | None = None,
        skip_confirm: bool = False,
        temporal_resolution: str = "daily",
        location_strategy: str = "auto",
        search_radius_km: float | None = None,
    ) -> pd.DataFrame:
        """Run exposure estimation. Returns the result DataFrame."""
        if not self.is_loaded:
            raise RuntimeError("No cohort loaded. Load data first.")

        if self.mode == "static":
            if pollutant is None:
                raise ValueError("Static mode requires a pollutant.")

            allowed = [*ALLOWED_POLLUTANTS, "all"]
            if pollutant not in allowed:
                raise ValueError(f"Invalid pollutant '{pollutant}'. Choose from: {allowed}")

            from aeris.exposure.estimators import ExposureEstimatorOpenAQStatic

            if pollutant == "all":
                last_df = pd.DataFrame()
                for p in ALLOWED_POLLUTANTS:
                    estimator = ExposureEstimatorOpenAQStatic(
                        input_csv=self.input_path,
                        pollutant=p,
                        api_key=self.config.openaq_api_key,
                        config=self.config,
                        country=country,
                        n_stations=n_stations,
                        outlier_detection=outlier_detection,
                        min_completeness=min_completeness,
                        cache=self.cache,
                        temporal_resolution=temporal_resolution,
                        location_strategy=location_strategy,
                        search_radius_km=search_radius_km,
                    )
                    result_df = estimator.run(skip_confirm=skip_confirm)
                    self.results[p] = result_df
                    last_df = result_df
                self.estimator = estimator
                self.decision_log.record(
                    Decision(
                        category="exposure_model",
                        choice="OpenAQ static estimation for ALL pollutants",
                        rationale="Multi-pollutant monitoring-network-based exposure assessment.",
                        data_context={
                            "pollutants": ALLOWED_POLLUTANTS,
                            "n_stations": n_stations,
                            "outlier_detection": outlier_detection,
                            "temporal_resolution": temporal_resolution,
                            "location_strategy": location_strategy,
                        },
                    )
                )
                return last_df
            else:
                estimator = ExposureEstimatorOpenAQStatic(
                    input_csv=self.input_path,
                    pollutant=pollutant,
                    api_key=self.config.openaq_api_key,
                    config=self.config,
                    country=country,
                    n_stations=n_stations,
                    outlier_detection=outlier_detection,
                    min_completeness=min_completeness,
                    cache=self.cache,
                    temporal_resolution=temporal_resolution,
                    location_strategy=location_strategy,
                    search_radius_km=search_radius_km,
                )
                result_df = estimator.run(skip_confirm=skip_confirm)
                self.results[pollutant] = result_df
                self.estimator = estimator

                rationale = "Monitoring-network-based exposure assessment"
                if n_stations > 1:
                    rationale += f" using IDW with {n_stations} stations"
                else:
                    rationale += " using nearest station"

                self.decision_log.record(
                    Decision(
                        category="exposure_model",
                        choice=f"OpenAQ static estimation for {pollutant.upper()}",
                        rationale=rationale + ".",
                        data_context={
                            "pollutant": pollutant,
                            "n_participants": len(result_df),
                            "n_with_data": len(result_df.dropna(subset=["mean"]))
                            if "mean" in result_df.columns
                            else "unknown",
                            "n_stations": n_stations,
                            "outlier_detection": outlier_detection,
                            "min_completeness": min_completeness,
                            "temporal_resolution": temporal_resolution,
                            "location_strategy": location_strategy,
                            "search_radius_km": search_radius_km,
                        },
                    )
                )
                return result_df

        else:  # dynamic
            if backend == "gmaps":
                from aeris.exposure.estimators import ExposureEstimatorGoogleMapsDynamic

                estimator = ExposureEstimatorGoogleMapsDynamic(
                    input_csv=self.input_path,
                    gmaps_api_key=self.config.google_maps_api_key,
                    min_completeness=min_completeness,
                )
            else:
                from aeris.exposure.estimators import ExposureEstimatorXGBDynamic

                estimator = ExposureEstimatorXGBDynamic(
                    input_csv=self.input_path,
                    purpleair_api_key=self.config.purpleair_api_key,
                    openaq_api_key=self.config.openaq_api_key,
                    model_path=self.config.xgb_model_path,
                    min_completeness=min_completeness,
                )

            result_df = estimator.run()
            self.results["all"] = result_df
            self.estimator = estimator

            self.decision_log.record(
                Decision(
                    category="exposure_model",
                    choice=f"Dynamic estimation ({backend} backend)",
                    rationale=f"GPS-tracked exposure assessment using {backend} backend.",
                    data_context={"backend": backend},
                )
            )
            return result_df

    def run_boundary_estimation(
        self,
        pollutant: str,
        start_date: str,
        end_date: str,
        iso3: str | None = None,
        adm_level: int | None = None,
        boundary_name: str | None = None,
        boundary_geojson_path: str | None = None,
        min_completeness: float | None = None,
        temporal_resolution: str = "daily",
        max_stations: int | None = None,
    ) -> pd.DataFrame:
        """Run explicit administrative-boundary exposure estimation."""
        from aeris.exposure.boundaries import boundary_from_geoboundaries, boundary_from_geojson
        from aeris.exposure.estimators import ExposureEstimatorOpenAQBoundary

        if self.cache is None:
            self.working_directory = str(Path.cwd())
            self.cache = ResponseCache(
                db_path=str(Path.cwd() / ".aeris_openaq_cache.sqlite"), ttl_hours=24 * 30
            )

        self._ensure_cache(Path(self.working_directory or Path.cwd()))

        if boundary_geojson_path:
            boundary = boundary_from_geojson(boundary_geojson_path, boundary_name)
        else:
            if iso3 is None or adm_level is None:
                raise ValueError(
                    "Provide boundary_geojson_path, or iso3, adm_level, and boundary_name."
                )
            boundary = boundary_from_geoboundaries(iso3, adm_level, boundary_name)

        estimator = ExposureEstimatorOpenAQBoundary(
            boundary=boundary,
            start_date=start_date,
            end_date=end_date,
            pollutant=pollutant,
            api_key=self.config.openaq_api_key,
            config=self.config,
            min_completeness=min_completeness,
            cache=self.cache,
            temporal_resolution=temporal_resolution,
            max_stations=max_stations,
        )
        result_df = estimator.run()
        self.results[pollutant] = result_df
        self.estimator = estimator
        self.boundary = boundary
        self.mode = "boundary"
        self.decision_log.record(
            Decision(
                category="exposure_model",
                choice=f"OpenAQ boundary estimation for {pollutant.upper()}: {boundary.name}",
                rationale=(
                    "Unweighted mean of monitor-level means within an explicit administrative "
                    "boundary; not a population-weighted area concentration or personal dose."
                ),
                data_context={
                    "boundary": boundary.provenance(),
                    "start_date": start_date,
                    "end_date": end_date,
                    "min_completeness": min_completeness,
                    "temporal_resolution": temporal_resolution,
                    "max_stations": max_stations,
                },
            )
        )
        return result_df

    @_single_checkpoint_writer
    def run_boundary_batch_estimation(
        self,
        pollutant: str,
        start_date: str,
        end_date: str,
        boundary_geojson_path: str,
        boundary_names: list[str] | None = None,
        min_completeness: float | None = None,
        temporal_resolution: str = "daily",
        checkpoint_path: str | None = None,
        max_stations: int | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
        """Estimate a deterministic, resumable collection of named boundaries."""
        from aeris.exposure.boundaries import boundary_names_from_geojson

        selected = boundary_names or boundary_names_from_geojson(boundary_geojson_path)
        selected = sorted(dict.fromkeys(selected), key=lambda value: value.casefold())
        checkpoint = Path(checkpoint_path).expanduser() if checkpoint_path else None
        summaries: list[dict] = []
        daily_rows: list[pd.DataFrame] = []
        errors: list[dict] = []
        completed: set[str] = set()
        request = {
            "pollutant": pollutant,
            "start_date": start_date,
            "end_date": end_date,
            "boundary_geojson_path": str(Path(boundary_geojson_path).resolve()),
            "boundary_geojson_sha256": hashlib.sha256(
                Path(boundary_geojson_path).read_bytes()
            ).hexdigest(),
            "boundary_names": selected,
            "min_completeness": min_completeness,
            "temporal_resolution": temporal_resolution,
            "max_stations": max_stations,
        }
        if checkpoint and checkpoint.exists():
            saved = json.loads(checkpoint.read_text(encoding="utf-8"))
            if saved.get("request") != request:
                raise ValueError("Checkpoint request does not match this batch.")
            summaries = list(saved.get("summaries", []))
            errors = list(saved.get("errors", []))
            completed = {row["boundary_name"] for row in summaries}
            daily_path = checkpoint.with_suffix(checkpoint.suffix + ".daily.csv")
            if daily_path.exists():
                saved_daily = pd.read_csv(daily_path)
                if not saved_daily.empty:
                    daily_rows.append(
                        saved_daily[saved_daily["boundary_name"].isin(completed)].copy()
                    )

        def save_checkpoint() -> None:
            if checkpoint is None:
                return
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            summary_path = checkpoint.with_suffix(checkpoint.suffix + ".summary.csv")
            _atomic_dataframe(summary_path, pd.DataFrame(summaries))
            daily_path = checkpoint.with_suffix(checkpoint.suffix + ".daily.csv")
            combined_daily = (
                pd.concat(daily_rows, ignore_index=True) if daily_rows else pd.DataFrame()
            )
            _atomic_dataframe(daily_path, combined_daily)
            _atomic_text(
                checkpoint,
                json.dumps(
                    {"schema_version": 1, "request": request, "summaries": summaries, "errors": errors},
                    indent=2,
                )
                + "\n",
            )

        for boundary_name in selected:
            if boundary_name in completed:
                continue
            errors = [row for row in errors if row["boundary_name"] != boundary_name]
            try:
                frame = self.run_boundary_estimation(
                    pollutant=pollutant,
                    start_date=start_date,
                    end_date=end_date,
                    boundary_name=boundary_name,
                    boundary_geojson_path=boundary_geojson_path,
                    min_completeness=min_completeness,
                    temporal_resolution=temporal_resolution,
                    max_stations=max_stations,
                )
                row = frame.to_dict(orient="records")[0]
                row["boundary_name"] = boundary_name
                if self.estimator is not None:
                    daily = self.estimator.get_daily_data()
                    if daily is not None and not daily.empty:
                        daily = daily.copy()
                        daily["boundary_name"] = boundary_name
                        daily_rows.append(daily)
                summaries.append(row)
            except Exception as exc:
                errors.append({"boundary_name": boundary_name, "error": str(exc)})
            save_checkpoint()

        summary_frame = pd.DataFrame(summaries)
        daily_frame = pd.concat(daily_rows, ignore_index=True) if daily_rows else pd.DataFrame()
        self.results[pollutant] = summary_frame
        self.batch_daily_results[pollutant] = daily_frame
        self.mode = "boundary_batch"
        return summary_frame, daily_frame, errors

    def plan_exposure(
        self,
        pollutant: str,
        country: str = "us",
        temporal_resolution: str = "daily",
        location_strategy: str = "auto",
        n_stations: int = 1,
        search_radius_km: float | None = None,
    ) -> dict:
        """Return an execution plan without retrieving any measurements."""
        if not self.is_loaded:
            raise RuntimeError("Load a cohort before planning exposure estimation.")
        if self.mode != "static":
            raise ValueError("Exposure planning is currently available for static cohorts only.")

        from aeris.exposure.estimators import ExposureEstimatorOpenAQStatic

        estimator = ExposureEstimatorOpenAQStatic(
            input_csv=self.input_path,
            pollutant=pollutant,
            api_key=self.config.openaq_api_key,
            country=country,
            n_stations=n_stations,
            cache=self.cache,
            temporal_resolution=temporal_resolution,
            location_strategy=location_strategy,
            search_radius_km=search_radius_km,
        )
        estimator.read_and_validate_input()
        calls, minutes, hours = estimator.estimate_api_calls()
        return {
            "source": "OpenAQ v3 with bounded public S3 archive fallback",
            "temporal_resolution": temporal_resolution,
            "location_strategy": location_strategy,
            "n_subjects": len(estimator.df_input),
            "n_stations_requested": n_stations,
            "search_radius_km": search_radius_km or self.config.search_radius / 1000,
            "estimated_calls_upper_bound": calls,
            "estimated_minutes_at_configured_limit": round(minutes, 2),
            "estimated_hours_at_configured_limit": round(hours, 3),
            "cache_path": self.cache.db_path if self.cache is not None else None,
            "notes": (
                "This is a conservative upper bound before station discovery. "
                "Repeated sensor/date-range requests are deduplicated during execution. "
                "When v3 returns no rows for a bounded historical window, AERIS checks "
                "OpenAQ's public S3 location-day archive and records the source."
            ),
        }

    def build_cohort_summary(self) -> dict:
        """Build a summary dict of the loaded cohort."""
        if self.cohort is None:
            return {}

        df = self.cohort
        summary: dict = {
            "n_participants": len(df),
            "mode": self.mode,
            "columns": df.columns.tolist(),
        }

        if "subject_id" in df.columns:
            summary["n_unique_subjects"] = int(df["subject_id"].nunique())

        if "start_date" in df.columns and "end_date" in df.columns:
            summary["date_range"] = f"{df['start_date'].min()} to {df['end_date'].max()}"

        if "zip" in df.columns:
            summary["n_zip_codes"] = int(df["zip"].nunique())
            summary["zip_examples"] = df["zip"].unique()[:5].tolist()

        if "address" in df.columns:
            summary["n_addresses"] = int(df["address"].nunique())

        if "latitude" in df.columns:
            summary["lat_range"] = (
                f"[{pd.to_numeric(df['latitude'], errors='coerce').min():.2f}, "
                f"{pd.to_numeric(df['latitude'], errors='coerce').max():.2f}]"
            )
        if "longitude" in df.columns:
            summary["lon_range"] = (
                f"[{pd.to_numeric(df['longitude'], errors='coerce').min():.2f}, "
                f"{pd.to_numeric(df['longitude'], errors='coerce').max():.2f}]"
            )

        return summary

    def build_data_context(self) -> str:
        """Build a data context string for LLM prompt injection."""
        parts: list[str] = []

        if self.cohort is not None:
            df = self.cohort
            parts.append(f"Cohort size: {len(df)} participants")
            parts.append(f"Mode: {self.mode}")
            parts.append(f"Columns: {', '.join(df.columns.tolist())}")

            if "start_date" in df.columns and "end_date" in df.columns:
                parts.append(f"Date range: {df['start_date'].min()} to {df['end_date'].max()}")

            if "zip" in df.columns:
                parts.append(f"Geographic coverage: {df['zip'].nunique()} unique ZIP codes")

            if "latitude" in df.columns and "longitude" in df.columns:
                lat_range = f"[{df['latitude'].min():.2f}, {df['latitude'].max():.2f}]"
                lon_range = f"[{df['longitude'].min():.2f}, {df['longitude'].max():.2f}]"
                parts.append(f"Lat range: {lat_range}, Lon range: {lon_range}")

        if self.results:
            for pollutant, result_df in self.results.items():
                if result_df is not None and not result_df.empty:
                    parts.append(f"\n{pollutant.upper()} exposure results:")
                    n_valid = len(
                        result_df.dropna(subset=["mean"])
                        if "mean" in result_df.columns
                        else result_df
                    )
                    cohort_n = len(self.cohort) if self.cohort is not None else "?"
                    parts.append(f"  Participants with data: {n_valid}/{cohort_n}")
                    if "mean" in result_df.columns:
                        parts.append(
                            f"  Exposure mean: {result_df['mean'].mean():.2f} "
                            f"(SD: {result_df['mean'].std():.2f})"
                        )
                        parts.append(
                            f"  Exposure range: [{result_df['mean'].min():.2f}, "
                            f"{result_df['mean'].max():.2f}]"
                        )
                    if "distance_m" in result_df.columns:
                        dist_km = result_df["distance_m"] / 1000
                        parts.append(f"  Median station distance: {dist_km.median():.1f} km")


        if self.working_directory:
            parts.append(f"\nWorking directory: {self.working_directory}")

        # Detect bundled demo folder
        demo_dir = Path(__file__).resolve().parent.parent.parent / "demo"
        if demo_dir.is_dir():
            parts.append(f"\nBundled demo folder: {demo_dir}")

        parts.append(f"\nWorkflow step: {self.workflow_step}/5")
        parts.append(f"Decisions logged: {len(self.decision_log)}")

        if not parts:
            return "No data loaded yet."

        return "\n".join(parts)

    def reload(self):
        """Reload hook (no-op for now)."""
        pass

"""Weights & Biases integration for fvspec benchmark tracking."""

from datetime import datetime
from pathlib import Path
from typing import Any, cast, TYPE_CHECKING

import wandb
from inspect_ai.solver import TaskState

from generate.config import WandbConfig
from generate.scaffold.dataset import Datapoint
from generate.scaffold.quality_assessment import QualityAssessment

if TYPE_CHECKING:
    from wandb.sdk.wandb_run import Run


class WandbLogger:
    """Manages wandb logging for fvspec benchmark runs.

    This class provides methods to:
    - Initialize wandb runs with appropriate metadata
    - Log per-sample metrics from QualityAssessment
    - Log artifacts (Lean code, QA JSON)
    - Support variant comparison via wandb groups
    """

    def __init__(self, config: WandbConfig):
        """Initialize the wandb logger.

        Args:
            config: Configuration for wandb logging
        """
        self.config = config
        self.run: "Run | None" = None
        self._sample_count = 0

    def init_run(
        self,
        variant: str,
        model: str,
        sample_size: int,
        ranseed: int,
        timestamp: str,
        group: str | None = None,
    ) -> None:
        """Initialize a wandb run for a benchmark evaluation.

        Args:
            variant: Prompt variant name
            model: Model name being evaluated
            sample_size: Number of samples in the dataset
            ranseed: Random seed used for sampling
            timestamp: Timestamp string for the run
            group: Optional group name for comparing multiple variants
        """
        if not self.config.enabled:
            return

        run_name = f"{variant}__{timestamp}"
        if group:
            run_name = f"{group}__{run_name}"

        artifacts_dir = Path.cwd() / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        self.run = wandb.init(
            project=self.config.project,
            entity=self.config.entity,
            name=run_name,
            group=group,
            tags=[variant, *self.config.tags],
            config={
                "variant": variant,
                "model": model,
                "sample_size": sample_size,
                "ranseed": ranseed,
                "timestamp": timestamp,
            },
            dir=str(artifacts_dir),
            reinit="return_previous",
        )

    def log_sample_metrics(
        self, qa: QualityAssessment, step: int | None = None
    ) -> None:
        """Log metrics from a completed sample to wandb.

        Args:
            qa: Quality assessment with computed metrics
            step: Optional step number (defaults to auto-incrementing sample count)
        """
        if not self.config.enabled or self.run is None:
            return

        if step is None:
            step = self._sample_count
            self._sample_count += 1

        metrics: dict[str, Any] = {
            "sample_id": qa.sample_id,
            "sample_name": qa.sample_name,
            # Performance metrics
            "token_usage": qa.token_usage,
            "time": qa.time,
            "num_messages": qa.num_messages,
            "num_generate_messages": qa.num_generate_messages,
            "num_input_messages": qa.num_input_messages,
            # Code metrics
            "success": 1 if qa.success else 0,
            "num_sorries": qa.num_sorries,
            "lines_pbt": qa.lines_pbt,
            "lines_code": qa.lines_code,
            "num_deps": qa.num_deps,
        }

        # Optional metrics
        if qa.percent_lines_added is not None:
            metrics["percent_lines_added"] = qa.percent_lines_added

        if qa.faithfulness_subjective is not None:
            metrics["faithfulness_subjective"] = qa.faithfulness_subjective

        if qa.interest_subjective is not None:
            metrics["interest_subjective"] = qa.interest_subjective

        # Structural faithfulness metrics
        if qa.structural_faithfulness is not None:
            sf = qa.structural_faithfulness
            metrics.update(
                {
                    "structural_faithfulness_overall": sf.overall,
                    "parameter_coverage": sf.parameter_coverage,
                    "type_correspondence": sf.type_correspondence,
                    "strategy_coverage": sf.strategy_coverage,
                    "assertion_coverage": sf.assertion_coverage,
                    "dependency_coverage": sf.dependency_coverage,
                }
            )

        self.run.log(metrics, step=step)

    def log_artifact(
        self,
        artifact_path: Path,
        artifact_type: str,
        name: str | None = None,
    ) -> None:
        """Log a file artifact to wandb.

        Args:
            artifact_path: Path to the artifact file
            artifact_type: Type of artifact (e.g., "lean_code", "qa_json")
            name: Optional name for the artifact (defaults to filename)
        """
        if not self.config.enabled or self.run is None:
            return

        if not artifact_path.exists():
            return

        artifact = wandb.Artifact(
            name=name or artifact_path.stem,
            type=artifact_type,
        )
        artifact.add_file(str(artifact_path))
        self.run.log_artifact(artifact)

    def log_sample_to_artifact(self, sample_dir: Path, sample_id: str) -> None:
        """Upload sample files to wandb run incrementally.

        This method uploads the sample's Lean code, QA JSON, and datapoint JSON
        directly to the wandb run using run.save(). Files are uploaded immediately
        and incrementally, so they're preserved even if the run is canceled.

        Args:
            sample_dir: Directory containing the sample's output files
            sample_id: Unique identifier for the sample
        """
        if not self.config.enabled or not self.config.upload_samples:
            return

        if self.run is None:
            return

        if not sample_dir.exists():
            return

        # Upload sample files directly to the run (incremental uploads)
        # Files appear in the wandb UI under "Files" tab for the run
        for file_path in sample_dir.glob("*"):
            if file_path.is_file() and file_path.suffix in {".lean", ".json"}:
                # Use run.save() to upload files incrementally
                # base_path determines the directory structure in wandb
                self.run.save(
                    str(file_path),
                    base_path=str(sample_dir.parent),
                    policy="now",
                )

    def log_summary_metrics(self, all_qa: list[QualityAssessment]) -> None:
        """Compute and log aggregate summary statistics across all samples.

        Args:
            all_qa: List of all quality assessments from the run
        """
        if not self.config.enabled or self.run is None or not all_qa:
            return

        # Compute aggregate statistics
        import statistics

        def safe_mean(values: list[float]) -> float:
            return statistics.mean(values) if values else 0.0

        def safe_stdev(values: list[float]) -> float:
            return statistics.stdev(values) if len(values) > 1 else 0.0

        # Extract metrics
        token_usage = [qa.token_usage for qa in all_qa]
        time = [qa.time for qa in all_qa]
        success_rate = [1 if qa.success else 0 for qa in all_qa]
        num_sorries = [qa.num_sorries for qa in all_qa if qa.success]
        lines_code = [qa.lines_code for qa in all_qa if qa.success]

        faithfulness_subj = [
            qa.faithfulness_subjective
            for qa in all_qa
            if qa.faithfulness_subjective is not None
        ]
        interest_subj = [
            qa.interest_subjective
            for qa in all_qa
            if qa.interest_subjective is not None
        ]

        structural_overall = [
            qa.structural_faithfulness.overall
            for qa in all_qa
            if qa.structural_faithfulness is not None
        ]

        summary = {
            # Aggregate performance
            "summary/total_samples": len(all_qa),
            "summary/success_rate": safe_mean(success_rate),
            "summary/mean_token_usage": safe_mean(token_usage),
            "summary/std_token_usage": safe_stdev(token_usage),
            "summary/mean_time": safe_mean(time),
            "summary/std_time": safe_stdev(time),
            # Aggregate code quality
            "summary/mean_num_sorries": safe_mean(num_sorries),
            "summary/mean_lines_code": safe_mean(lines_code),
            # Aggregate subjective metrics
            "summary/mean_faithfulness_subjective": safe_mean(faithfulness_subj),
            "summary/std_faithfulness_subjective": safe_stdev(faithfulness_subj),
            "summary/mean_interest_subjective": safe_mean(interest_subj),
            "summary/std_interest_subjective": safe_stdev(interest_subj),
            # Aggregate structural faithfulness
            "summary/mean_structural_faithfulness": safe_mean(structural_overall),
            "summary/std_structural_faithfulness": safe_stdev(structural_overall),
        }

        # Log to wandb summary (persists after run completes)
        for key, value in summary.items():
            self.run.summary[key] = value

    def download_dep_cache(self) -> Path | None:
        """Download the latest dependency cache from wandb artifacts.

        Returns:
            Path to the cache directory if successful, None otherwise
        """
        if not self.config.enabled or not self.config.sync_dep_cache:
            return None

        if self.run is None:
            return None

        try:
            # Try to use the latest dep cache artifact
            artifact = self.run.use_artifact(
                "dep-cache:latest", type="dependency-cache"
            )
            cache_dir = Path.cwd() / "artifacts" / "depcache"
            artifact.download(root=str(cache_dir))
            return cache_dir
        except Exception as e:
            # Artifact doesn't exist yet (first run) or download failed
            print(f"Note: Could not download dep cache: {e}")
            return None

    def upload_dep_cache(self) -> None:
        """Upload the current dependency cache to wandb artifacts.

        Creates a new version of the dep-cache artifact with the current state
        of the local dependency cache.
        """
        if not self.config.enabled or not self.config.sync_dep_cache:
            return

        if self.run is None:
            return

        cache_dir = Path.cwd() / "artifacts" / "depcache"
        if not cache_dir.exists() or not any(cache_dir.iterdir()):
            # No cache to upload
            return

        try:
            artifact = wandb.Artifact(
                name="dep-cache",
                type="dependency-cache",
                description="Cached dependency formalizations",
                metadata={
                    "updated_at": datetime.now().isoformat(),
                },
            )

            # Add entire cache directory
            artifact.add_dir(str(cache_dir))

            # Log the artifact
            self.run.log_artifact(artifact)
        except Exception as e:
            print(f"Warning: Could not upload dep cache: {e}")

    def finish(self) -> None:
        """Finish the wandb run."""
        if self.run is not None:
            self.run.finish()
            self.run = None


# Global logger instance (initialized on first use)
_logger: WandbLogger | None = None


def init_wandb_logger(config: WandbConfig) -> WandbLogger:
    """Initialize the global wandb logger instance.

    Args:
        config: Configuration for wandb logging

    Returns:
        The initialized wandb logger
    """
    global _logger
    _logger = WandbLogger(config)
    return _logger


def get_wandb_logger() -> WandbLogger | None:
    """Get the current wandb logger instance.

    Returns:
        The wandb logger, or None if not initialized
    """
    return _logger


def log_sample_to_wandb(state: TaskState) -> None:
    """Log metrics and artifacts for a completed sample to wandb.

    This function is designed to be called from the write_to_disk cleanup function.
    It logs both per-sample metrics and uploads sample files to the run artifact.

    Args:
        state: The task state after sample completion
    """
    logger = get_wandb_logger()
    if logger is None or not logger.config.enabled:
        return

    # Extract quality assessment
    qa = QualityAssessment.from_task_state(state)
    logger.log_sample_metrics(qa)

    # Upload sample files to run artifact
    date_time = cast(str, state.metadata.get("date_time"))
    variant = cast(str, state.metadata.get("variant"))
    sample_id = str(state.sample_id)

    from generate.scaffold.tools import utilio

    # Get the sample directory
    sample_dir = utilio.get_sample_output_dir(date_time, sample_id, variant)

    # Log all sample files to the run artifact incrementally
    logger.log_sample_to_artifact(sample_dir, sample_id)

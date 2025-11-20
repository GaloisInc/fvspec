"""Weights & Biases integration for fvspec benchmark tracking."""

import statistics
from pathlib import Path
from typing import TYPE_CHECKING, cast

import wandb
from inspect_ai.solver import TaskState

from generate.config import WandbConfig
from generate.scaffold.quality_assessment import QualityAssessment
from generate.scaffold.tools import utilio

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
        self.run: Run | None = None
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

        This method now delegates to QualityAssessment.to_wandb_metrics()
        to maintain a single source of truth for metric definitions.

        Args:
            qa: Quality assessment with computed metrics
            step: Optional step number (defaults to auto-incrementing sample count)
        """
        if not self.config.enabled or self.run is None:
            return

        if step is None:
            step = self._sample_count
            self._sample_count += 1

        # Use centralized metric export from QualityAssessment
        metrics = qa.to_wandb_metrics()

        self.run.log(metrics, step=step)

    def log_sample_files(self, sample_dir: Path) -> None:
        """Upload sample files to wandb run incrementally.

        This method uploads the sample's Lean code, QA JSON, and datapoint JSON
        directly to the wandb run using run.save(). Files are uploaded immediately
        and incrementally, so they're preserved even if the run is canceled.

        Files appear in the wandb UI under "Files" tab for the run, organized by
        the directory structure: <timestamp>__<variant>/<sample_id>__<pbt_name>/

        Args:
            sample_dir: Directory containing the sample's output files
                       (e.g., artifacts/runs/2025-11-10T15-18-13__control-functional/10104_test_foo/)
        """
        if not self.config.enabled or not self.config.upload_samples:
            return

        if self.run is None:
            return

        if not sample_dir.exists():
            return

        # Upload sample files directly to the run (incremental uploads)
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

        # Plausible metrics
        plausible_ran = [1 if qa.plausibility.ran else 0 for qa in all_qa]
        plausible_success_rates = [
            qa.plausibility.success for qa in all_qa if qa.plausibility.ran
        ]
        plausible_time_values = [
            qa.plausibility.time
            for qa in all_qa
            if qa.plausibility.ran and qa.plausibility.time is not None
        ]
        plausible_counterexample_counts = [
            qa.plausibility.counterexamples
            for qa in all_qa
            if qa.plausibility.ran and qa.plausibility.counterexamples > 0
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
            # Aggregate plausible metrics
            "summary/plausible_run_rate": safe_mean(plausible_ran),
            "summary/plausible_mean_success_rate": safe_mean(plausible_success_rates),
            "summary/plausible_std_success_rate": safe_stdev(plausible_success_rates),
            "summary/mean_plausible_time": safe_mean(plausible_time_values),
            "summary/std_plausible_time": safe_stdev(plausible_time_values),
            "summary/total_counterexamples": sum(plausible_counterexample_counts),
            "summary/samples_with_counterexamples": len(
                plausible_counterexample_counts
            ),
        }

        # Log to wandb summary (persists after run completes)
        for key, value in summary.items():
            self.run.summary[key] = value

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
    """Log metrics and files for a completed sample to wandb.

    This function is designed to be called from the write_to_disk cleanup function.
    It logs both per-sample metrics and uploads sample files to the run.

    Args:
        state: The task state after sample completion
    """
    logger = get_wandb_logger()
    if logger is None or not logger.config.enabled:
        return

    # Extract quality assessment
    qa = QualityAssessment.from_task_state(state)
    logger.log_sample_metrics(qa)

    # Upload sample files to run
    date_time = cast(str, state.metadata.get("date_time"))
    variant = cast(str, state.metadata.get("variant"))
    sample_id = str(state.sample_id)

    # Get the sample directory
    sample_dir = utilio.get_sample_output_dir(date_time, sample_id, variant)

    # Upload all sample files to the run incrementally
    logger.log_sample_files(sample_dir)

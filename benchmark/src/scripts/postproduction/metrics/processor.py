"""JSONL processing for metrics augmentation."""

import json
from datetime import datetime
from pathlib import Path
from time import time
from typing import Any

from rich.console import Console
from rich.progress import track

from scripts.postproduction.metrics.lean_parser import extract_all_metrics
from scripts.postproduction.metrics.models import LeanCodeMetrics, MetricsMetadata

console = Console()

METRICS_VERSION = "1.0.0"


def process_jsonl(
    input_file: Path,
    output_file: Path,
    limit: int | None = None,
    start_idx: int | None = None,
    stop_idx: int | None = None,
    retry_failed: bool = False,
) -> dict[str, int]:
    """Process JSONL file and augment with Lean metrics.

    Args:
        input_file: Path to input JSONL file
        output_file: Path to output JSONL file
        limit: Only process first N samples (mutually exclusive with start/stop)
        start_idx: Start processing from this index (0-based, inclusive)
        stop_idx: Stop processing at this index (0-based, exclusive)
        retry_failed: Also retry samples with metrics_error field

    Returns:
        Dict with statistics: total_read, total_computed, skipped, errors
    """
    stats = {"total_read": 0, "total_computed": 0, "skipped": 0, "errors": 0}

    # Determine effective range
    effective_start = start_idx if start_idx is not None else 0
    effective_stop = stop_idx  # None means process to end

    # Read all samples
    samples = []
    with input_file.open("r") as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))

    stats["total_read"] = len(samples)

    # Apply limit if specified
    if limit is not None:
        effective_stop = min(len(samples), effective_start + limit)

    # Process samples with progress bar
    with output_file.open("w") as out:
        for idx, sample in track(
            enumerate(samples),
            total=len(samples),
            description="Computing Lean metrics",
        ):
            # Check if we should process this sample
            should_process = _should_process_sample(
                idx, sample, effective_start, effective_stop, retry_failed
            )

            if should_process:
                try:
                    # Extract Lean code from sample
                    spec_code = sample.get("spec")
                    impl_code = sample.get("impl")
                    tests_code = sample.get("tests")

                    # Compute metrics
                    start_time = time()
                    metrics_data = extract_all_metrics(spec_code, impl_code, tests_code)
                    computation_time = time() - start_time

                    # Create metrics objects
                    lean_metrics = LeanCodeMetrics(**metrics_data)

                    metadata = MetricsMetadata(
                        version=METRICS_VERSION,
                        timestamp=datetime.now(),
                        computation_time_seconds=computation_time,
                        spec_available=spec_code is not None,
                        impl_available=impl_code is not None,
                        tests_available=tests_code is not None,
                    )

                    # Augment sample with metrics
                    sample["lean_metrics"] = lean_metrics.model_dump(mode="json")
                    sample["metrics_metadata"] = metadata.model_dump(mode="json")

                    # Remove error field if present (successful computation)
                    if "metrics_error" in sample:
                        del sample["metrics_error"]

                    stats["total_computed"] += 1

                except Exception as e:
                    # Record error in sample
                    sample["metrics_error"] = str(e)
                    stats["errors"] += 1

                    # Remove metrics fields if present
                    if "lean_metrics" in sample:
                        del sample["lean_metrics"]
                    if "metrics_metadata" in sample:
                        del sample["metrics_metadata"]

            else:
                stats["skipped"] += 1

            # Write sample to output (all samples, modified or not)
            out.write(json.dumps(sample) + "\n")

    return stats


def _should_process_sample(
    idx: int,
    sample: dict[str, Any],
    start_idx: int,
    stop_idx: int | None,
    retry_failed: bool,
) -> bool:
    """Determine if a sample should be processed.

    Args:
        idx: Current sample index
        sample: Sample data
        start_idx: Start index for processing
        stop_idx: Stop index for processing (None = no limit)
        retry_failed: Whether to retry samples with errors

    Returns:
        True if sample should be processed
    """
    # Check index range
    if idx < start_idx:
        return False
    if stop_idx is not None and idx >= stop_idx:
        return False

    # Check if already has metrics (skip unless retry_failed)
    has_metrics = "lean_metrics" in sample and "metrics_metadata" in sample
    has_error = "metrics_error" in sample

    # Default behavior: process if missing metrics
    if not has_metrics and not has_error:
        return True

    # Retry mode: also process samples with errors
    if retry_failed and has_error:
        return True

    # Skip already-computed samples
    return False


def get_sample_summary(sample: dict[str, Any]) -> str:
    """Get a summary string for a sample.

    Args:
        sample: Sample data

    Returns:
        Summary string (sample_id and name)
    """
    sample_id = sample.get("sample_id", "unknown")
    sample_name = sample.get("realpbt_sample_name", "unknown")
    return f"{sample_id}_{sample_name}"

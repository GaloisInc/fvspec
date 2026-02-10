"""Core grading logic."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

from scripts.postproduction.grader.client import AnthropicGraderClient
from scripts.postproduction.grader.models import DifficultyGrade, GraderMetadata
from scripts.postproduction.grader.prompts import (
    load_system_prompt,
    render_difficulty_prompt,
)

console = Console()


def grade_sample(
    sample: dict[str, Any],
    client: AnthropicGraderClient,
) -> dict[str, Any]:
    """Grade a single sample for difficulty.

    Args:
        sample: Sample dictionary from merged JSONL
        client: Anthropic client for API calls

    Returns:
        Sample dictionary augmented with grading fields
    """
    start_time = time.time()
    difficulty_grade: DifficultyGrade | None = None
    grader_error: str | None = None

    system_prompt = load_system_prompt()

    # Grade difficulty
    try:
        difficulty_prompt = render_difficulty_prompt(sample)
        difficulty_grade, tokens, _ = client.grade_difficulty(
            system_prompt, difficulty_prompt
        )

        if difficulty_grade is None:
            grader_error = "Difficulty grading failed (API error or no response)"
    except Exception as e:
        grader_error = f"Difficulty grading error: {str(e)}"
        console.print(f"[red]{grader_error}[/red]")
        tokens = 0

    elapsed = time.time() - start_time

    # Create metadata
    metadata = GraderMetadata(
        model=client.model,
        timestamp=datetime.now().isoformat(),
        tokens_used=tokens,
        grading_time_seconds=elapsed,
    )

    # Augment sample with grading results
    graded_sample = {
        **sample,
        "grader_metadata": metadata.model_dump(),
    }

    # Add difficulty fields with renamed keys
    if difficulty_grade:
        graded_sample["difficulty_subjective_haiku"] = difficulty_grade.score
        graded_sample["difficulty_subjective_haiku_takes"] = (
            difficulty_grade.haiku_takes
        )
    else:
        graded_sample["difficulty_subjective_haiku"] = None
        graded_sample["difficulty_subjective_haiku_takes"] = None

    if grader_error:
        graded_sample["grader_error"] = grader_error

    return graded_sample


def process_jsonl(
    input_file: Path,
    output_file: Path,
    client: AnthropicGraderClient,
    limit: int | None = None,
    start_idx: int | None = None,
    stop_idx: int | None = None,
    retry_failed: bool = False,
) -> dict[str, int]:
    """Process a JSONL file, grading each sample for difficulty and writing to output.

    The output file is a COMPLETE COPY of the input file, with grading fields
    added to the samples that were graded. Samples not graded pass through unchanged.

    Resume-safe: If output file exists, already-graded samples are reused (by sample name).

    Args:
        input_file: Input JSONL file path
        output_file: Output JSONL file path
        client: Anthropic client for API calls
        limit: Limit number of samples to grade (None = all)
        start_idx: Start grading from this index (0-based, inclusive)
        stop_idx: Stop grading at this index (0-based, exclusive)
        retry_failed: Only grade samples with grader_error field

    Returns:
        Statistics about the grading operation
    """
    stats = {
        "total_read": 0,
        "total_graded": 0,
        "skipped": 0,
        "reused": 0,
        "errors": 0,
    }

    # Load existing graded samples from output file (if exists) for resume support
    existing_graded: dict[int, dict[str, Any]] = {}
    if output_file.exists() and input_file != output_file:
        console.print(f"[cyan]Loading existing grades from {output_file}...[/cyan]")
        with open(output_file) as f:
            for line in f:
                if line.strip():
                    sample = json.loads(line)
                    sample_id = sample.get("sample_id")
                    # Only reuse if successfully graded (has difficulty field, no error)
                    has_grade = "difficulty_subjective_haiku" in sample
                    has_error = "grader_error" in sample
                    if sample_id and has_grade and (not has_error or not retry_failed):
                        existing_graded[sample_id] = sample
        console.print(
            f"[cyan]Found {len(existing_graded)} existing grades to reuse[/cyan]"
        )

    # Read all samples from input
    all_samples = []
    with open(input_file) as f:
        for line in f:
            if line.strip():
                sample = json.loads(line)
                all_samples.append(sample)

    stats["total_read"] = len(all_samples)

    # Helper to check if sample needs grading
    def needs_grading(sample: dict[str, Any]) -> bool:
        sample_id = sample.get("sample_id")
        # If we have an existing grade from output file, don't re-grade
        if sample_id and sample_id in existing_graded:
            return False
        # Grade if missing difficulty fields in input
        if "difficulty_subjective_haiku" not in sample:
            return True
        # Grade if has error and retry_failed is set
        if retry_failed and "grader_error" in sample:
            return True
        return False

    # Determine which samples to grade (by index)
    indices_to_grade = set()

    if start_idx is not None or stop_idx is not None:
        # Grade samples in [start, stop) range
        start = start_idx if start_idx is not None else 0
        stop = stop_idx if stop_idx is not None else len(all_samples)
        # Within range, grade missing samples (and errors if retry_failed)
        for i in range(start, min(stop, len(all_samples))):
            if needs_grading(all_samples[i]):
                indices_to_grade.add(i)
        console.print(
            f"[cyan]Grading samples {start} to {stop} "
            f"(found {len(indices_to_grade)} to grade)[/cyan]"
        )
    elif limit is not None:
        # Grade first N missing/error samples
        for i, sample in enumerate(all_samples):
            if len(indices_to_grade) >= limit:
                break
            if needs_grading(sample):
                indices_to_grade.add(i)
        console.print(f"[cyan]Grading first {len(indices_to_grade)} samples[/cyan]")
    else:
        # Grade all missing samples (and errors if retry_failed)
        for i, sample in enumerate(all_samples):
            if needs_grading(sample):
                indices_to_grade.add(i)
        msg = f"Found {len(indices_to_grade)} samples to grade"
        if retry_failed:
            msg += " (missing + errors)"
        console.print(f"[cyan]{msg}[/cyan]")

    # Process all samples and write complete output
    with open(output_file, "w") as outfile:
        for i, sample in enumerate(all_samples):
            name = sample.get("realpbt_sample_name")
            sample_id = sample.get("sample_id")

            if i in indices_to_grade:
                # Grade this sample
                console.print(
                    f"[cyan]Grading sample {stats['total_graded'] + 1}/{len(indices_to_grade)}: "
                    f"{name or 'unknown'}[/cyan]"
                )

                try:
                    graded_sample = grade_sample(
                        sample,
                        client,
                    )

                    # Write graded sample
                    outfile.write(json.dumps(graded_sample) + "\n")
                    outfile.flush()  # Ensure it's written to disk

                    stats["total_graded"] += 1

                    if "grader_error" in graded_sample:
                        stats["errors"] += 1

                except Exception as e:
                    console.print(f"[red]Failed to process sample: {e}[/red]")
                    # Write sample with error field
                    error_sample = {
                        **sample,
                        "grader_error": f"Processing error: {str(e)}",
                    }
                    outfile.write(json.dumps(error_sample) + "\n")
                    outfile.flush()
                    stats["errors"] += 1
            elif sample_id and sample_id in existing_graded:
                # Reuse existing grade from output file (merge into current sample)
                graded_fields = {
                    k: v
                    for k, v in existing_graded[sample_id].items()
                    if k
                    in (
                        "difficulty_subjective_haiku",
                        "difficulty_subjective_haiku_takes",
                        "grader_metadata",
                    )
                }
                merged = {**sample, **graded_fields}
                outfile.write(json.dumps(merged) + "\n")
                stats["reused"] += 1
            else:
                # Pass through unchanged (already graded in input)
                outfile.write(json.dumps(sample) + "\n")
                stats["skipped"] += 1

    return stats

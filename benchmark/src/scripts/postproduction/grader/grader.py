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
        "grader_difficulty": (
            difficulty_grade.model_dump() if difficulty_grade else None
        ),
        "grader_metadata": metadata.model_dump(),
    }

    if grader_error:
        graded_sample["grader_error"] = grader_error

    return graded_sample


def process_jsonl(
    input_file: Path,
    output_file: Path,
    client: AnthropicGraderClient,
    limit: int | None = None,
    retry_failed: bool = False,
) -> dict[str, int]:
    """Process a JSONL file, grading each sample for difficulty and writing to output.

    The output file is a COMPLETE COPY of the input file, with grading fields
    added to the samples that were graded. Samples not graded pass through unchanged.

    Args:
        input_file: Input JSONL file path
        output_file: Output JSONL file path
        client: Anthropic client for API calls
        limit: Limit number of samples to grade (None = all)
        retry_failed: Only grade samples with grader_error field

    Returns:
        Statistics about the grading operation
    """
    stats = {
        "total_read": 0,
        "total_graded": 0,
        "skipped": 0,
        "errors": 0,
    }

    # Read all samples
    all_samples = []
    with open(input_file) as f:
        for line in f:
            if line.strip():
                sample = json.loads(line)
                all_samples.append(sample)

    stats["total_read"] = len(all_samples)

    # Determine which samples to grade (by index)
    indices_to_grade = set()

    if retry_failed:
        # Only grade samples with grader_error
        for i, sample in enumerate(all_samples):
            if "grader_error" in sample:
                indices_to_grade.add(i)
        console.print(
            f"[cyan]Found {len(indices_to_grade)} samples with errors to retry[/cyan]"
        )
    elif limit is not None:
        # Grade first N samples
        indices_to_grade = set(range(min(limit, len(all_samples))))
        console.print(f"[cyan]Grading first {len(indices_to_grade)} samples[/cyan]")
    else:
        # Grade all samples
        indices_to_grade = set(range(len(all_samples)))
        console.print(f"[cyan]Grading all {len(indices_to_grade)} samples[/cyan]")

    # Process all samples and write complete output
    with open(output_file, "w") as outfile:
        for i, sample in enumerate(all_samples):
            if i in indices_to_grade:
                # Grade this sample
                console.print(
                    f"[cyan]Grading sample {stats['total_graded'] + 1}/{len(indices_to_grade)}: "
                    f"{sample.get('name', 'unknown')}[/cyan]"
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
            else:
                # Pass through unchanged
                outfile.write(json.dumps(sample) + "\n")
                stats["skipped"] += 1

    return stats

"""Core grading logic with Jinja2 template rendering."""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader
from rich.console import Console

from .client import AnthropicGraderClient
from .models import DifficultyGrade, GraderMetadata, QualityGrade

console = Console()

# Template loading
TEMPLATES_DIR = Path(__file__).parent / "prompts"
jinja_env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))


def load_system_prompt() -> str:
    """Load the shared system prompt.

    Returns:
        System prompt text
    """
    system_template = jinja_env.get_template("system.prompt")
    return system_template.render()


def render_quality_prompt(sample: dict[str, Any]) -> str:
    """Render the quality assessment prompt with sample data.

    Args:
        sample: Sample dictionary from merged JSONL

    Returns:
        Rendered quality prompt
    """
    template = jinja_env.get_template("quality.prompt.template")

    # Extract context for quality assessment
    context = {
        "pbt_code": sample.get("code", ""),
        "pbt_summary": sample.get("summary", ""),
        "spec_code": sample.get("spec"),  # May be None
        "impl_code": sample.get("impl"),  # May be None
        "success": sample.get("success", False),
        "num_theorems": sample.get("num_theorems", 0),
        "num_sorries": sample.get("num_sorries", 0),
        "structural_faithfulness": sample.get("structural_faithfulness", {}),
        "plausibility": sample.get("plausibility", {}),
    }

    return template.render(**context)


def render_difficulty_prompt(sample: dict[str, Any]) -> str:
    """Render the difficulty estimation prompt with sample data.

    Args:
        sample: Sample dictionary from merged JSONL

    Returns:
        Rendered difficulty prompt
    """
    template = jinja_env.get_template("difficulty.prompt.template")

    # Extract context for difficulty assessment
    context = {
        "pbt_code": sample.get("code", ""),
        "pbt_summary": sample.get("summary", ""),
        "radon": sample.get("radon", {}),
        "deps": sample.get("deps", []),
        "dep_names": sample.get("dep_names", []),
        "num_theorems": sample.get("num_theorems", 0),
        "implementation_level": sample.get("implementation_level", ""),
        "variant": sample.get("variant", ""),
    }

    return template.render(**context)


def grade_sample(
    sample: dict[str, Any],
    client: AnthropicGraderClient,
    skip_quality: bool = False,
    skip_difficulty: bool = False,
) -> dict[str, Any]:
    """Grade a single sample for quality and difficulty.

    Args:
        sample: Sample dictionary from merged JSONL
        client: Anthropic client for API calls
        skip_quality: Skip quality assessment
        skip_difficulty: Skip difficulty assessment

    Returns:
        Sample dictionary augmented with grading fields
    """
    start_time = time.time()
    total_tokens = 0
    quality_tokens = 0
    difficulty_tokens = 0

    quality_grade: QualityGrade | None = None
    difficulty_grade: DifficultyGrade | None = None
    grader_error: str | None = None

    system_prompt = load_system_prompt()

    # Grade quality
    if not skip_quality:
        try:
            quality_prompt = render_quality_prompt(sample)
            quality_grade, tokens, _ = client.grade_quality(
                system_prompt, quality_prompt
            )
            quality_tokens = tokens
            total_tokens += tokens

            if quality_grade is None:
                grader_error = "Quality grading failed (API error or no response)"
        except Exception as e:
            grader_error = f"Quality grading error: {str(e)}"
            console.print(f"[red]{grader_error}[/red]")

    # Grade difficulty
    if not skip_difficulty:
        try:
            difficulty_prompt = render_difficulty_prompt(sample)
            difficulty_grade, tokens, _ = client.grade_difficulty(
                system_prompt, difficulty_prompt
            )
            difficulty_tokens = tokens
            total_tokens += tokens

            if difficulty_grade is None:
                if grader_error:
                    grader_error += "; Difficulty grading failed"
                else:
                    grader_error = (
                        "Difficulty grading failed (API error or no response)"
                    )
        except Exception as e:
            error_msg = f"Difficulty grading error: {str(e)}"
            if grader_error:
                grader_error += f"; {error_msg}"
            else:
                grader_error = error_msg
            console.print(f"[red]{error_msg}[/red]")

    elapsed = time.time() - start_time

    # Create metadata
    metadata = GraderMetadata(
        model=client.model,
        timestamp=datetime.now().isoformat(),
        tokens_used=total_tokens,
        quality_tokens=quality_tokens,
        difficulty_tokens=difficulty_tokens,
        grading_time_seconds=elapsed,
    )

    # Augment sample with grading results
    graded_sample = {
        **sample,
        "grader_quality": quality_grade.model_dump() if quality_grade else None,
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
    skip_quality: bool = False,
    skip_difficulty: bool = False,
    retry_failed: bool = False,
) -> dict[str, int]:
    """Process a JSONL file, grading each sample and writing to output.

    The output file is a COMPLETE COPY of the input file, with grading fields
    added to the samples that were graded. Samples not graded pass through unchanged.

    Args:
        input_file: Input JSONL file path
        output_file: Output JSONL file path
        client: Anthropic client for API calls
        limit: Limit number of samples to grade (None = all)
        skip_quality: Skip quality assessment
        skip_difficulty: Skip difficulty assessment
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
                        skip_quality=skip_quality,
                        skip_difficulty=skip_difficulty,
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

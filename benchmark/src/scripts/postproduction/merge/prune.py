"""Schema pruning and transformation for merged samples.

This module provides functions for cleaning up the merged sample schema:
- Removing unnecessary fields
- Renaming fields for consistency
- Reordering fields for better readability

To customize schema transformations, edit the configuration constants below:
- FIELDS_TO_REMOVE: Set of field names to exclude from output
- FIELD_RENAMES: Dictionary mapping old field names to new names
- FIELD_ORDER: List defining the order of fields in output (unlisted fields appear after in alphabetical order)

Examples:
    Remove fields:
        FIELDS_TO_REMOVE = {"debug_info", "internal_id", "temp_data"}

    Rename fields:
        FIELD_RENAMES = {"old_name": "new_name", "impl_code": "implementation"}

    Reorder fields:
        FIELD_ORDER = ["sample_id", "name", "code", ...]
"""

import re
from typing import Any

# Fields to remove from the final output
FIELDS_TO_REMOVE = {
    "run_provenance",
    # not informative
    "has_unit_tests",
    "id",  # redundant with sample_id
    # Realpbt metadata fields - not needed for benchmark
    "hash",
    "summary_vector",
    "summaryversion",
    "summaryconfidence",
    "mode",
    "start_line",
    "end_line",
    "source",
    "source_file",
    # No variation fields (single value across all samples)
    "has_eval_statements",  # bool, 1 class
    "has_unit_stub",  # bool, 1 class
    "impl_eval_stripped",  # bool, 1 class
    "lines_code",  # int64, 0-0
    "num_eval_statements",  # int64, 0-0
    "num_generate_messages",  # int64, 0-0
    "num_input_messages",  # int64, 1-1
    "num_messages",  # int64, 1-1
    "num_sorries",  # int64, 0-0
    "num_trivial_unit_theorems",  # int64, 0-0
    "num_unit_tests",  # int64, 0-0
    "percent_lines_added",  # float64, -1--1
    "spec_sig_success",  # bool, 1 class
    "unit_tests_available",  # bool, 1 class
    "model",  # all sonnet 4.5
    "variant",  # all `control-functional`
    # Null/empty fields (no data)
    "faithfulness_subjective",  # null
    "interest_subjective",  # null
    "percent_plausible",  # null
    "plausibility",
    # Noise
    "datetime",  # temporal metadata, not useful
    "function_discovery",
    "sample_name",
}

# Field renames: old_name -> new_name
# Fields from realpbt dataset (https://huggingface.co/datasets/Benchify/realpbt)
# are prefixed with "realpbt_" for clarity
FIELD_RENAMES = {
    # Core realpbt fields from Datapoint model
    # Note: 'id' is removed (redundant with sample_id)
    # 'original_id' becomes 'realpbt_id' (FK to HuggingFace realpbt dataset)
    "original_id": "realpbt_id",
    "radon": "realpbt_radon",
    "repo_id": "realpbt_repo_id",
    "name": "realpbt_sample_name",
    "code": "realpbt_code",
    "source_file": "realpbt_source_file",
    "start_line": "realpbt_start_line",
    "end_line": "realpbt_end_line",
    "dep_names": "realpbt_dep_names",
    "deps": "realpbt_deps",
    "source": "realpbt_source",
    "summary": "realpbt_summary",
    "mode": "realpbt_mode",
    "lines_pbt": "realpbt_lines_pbt",
    # Note: id, hash, summary_vector, summaryversion, summaryconfidence are removed (see FIELDS_TO_REMOVE)
}

# Desired field order (fields not listed will appear after these in alphabetical order)
FIELD_ORDER = [
    # Benchmark-generated identifiers
    "sample_id",
    "realpbt_sample_name",
    # Generated Lean code
    "spec",
    "impl",
    # RealPBT source data
    "realpbt_id",
    "realpbt_name",
    "realpbt_repo_id",
    "realpbt_code",
    "realpbt_summary",
    # Results
    "num_theorems",
    # Metadata fields follow alphabetically
]


def prune_sample(sample: dict[str, Any]) -> dict[str, Any] | None:
    """Apply pruning transformations to a sample.

    Args:
        sample: Sample dictionary to transform

    Returns:
        Transformed sample dictionary, or None if sample should be filtered out.
        Transformations applied:
        - Removed fields excluded
        - Fields renamed according to FIELD_RENAMES
        - Fields reordered according to FIELD_ORDER
        - impl_autoform_success transformed from bool to 0/0.5/1 scale
        - num_theorems recomputed from spec field (fixes buggy original count)
        - Filters out samples with success=False (pipeline failures)
    """
    # Step 0: Filter out failed samples (success=False indicates pipeline failure)
    if not sample.get("success", True):
        return None

    # Step 1: Remove fields
    pruned = {k: v for k, v in sample.items() if k not in FIELDS_TO_REMOVE}

    # Step 2: Transform impl_autoform_success from bool to 0/0.5/1 scale
    # - 1.0: impl_autoform_success=True AND no sorry in impl (fully implemented)
    # - 0.5: impl_autoform_success=True BUT has sorry in impl (structured but stubbed)
    # - 0.0: impl_autoform_success=False (failed to generate valid structure)
    if "impl_autoform_success" in pruned:
        impl_success = pruned["impl_autoform_success"]
        impl_code = pruned.get("impl", "")
        has_sorry = "sorry" in impl_code if impl_code else False

        if impl_success is True:
            pruned["impl_autoform_success"] = 0.5 if has_sorry else 1.0
        else:
            pruned["impl_autoform_success"] = 0.0

    # Step 3: Recompute num_theorems from spec field
    # The original num_theorems field was buggy (always 0), so recompute it
    # by counting 'theorem' and 'lemma' keywords in the spec
    if "num_theorems" in pruned:
        spec = pruned.get("spec", "")
        if spec:
            # Count theorem and lemma declarations
            theorem_count = len(re.findall(r"\btheorem\b", spec))
            lemma_count = len(re.findall(r"\blemma\b", spec))
            pruned["num_theorems"] = theorem_count + lemma_count
        else:
            pruned["num_theorems"] = 0

    # Step 4: Rename fields
    for old_name, new_name in FIELD_RENAMES.items():
        if old_name in pruned:
            pruned[new_name] = pruned.pop(old_name)

    # Step 5: Reorder fields
    ordered = {}

    # Add fields in specified order first
    for field in FIELD_ORDER:
        if field in pruned:
            ordered[field] = pruned[field]

    # Add remaining fields in alphabetical order
    remaining = sorted(k for k in pruned.keys() if k not in ordered)
    for field in remaining:
        ordered[field] = pruned[field]

    return ordered


def prune_samples(samples: dict[int, dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Apply pruning transformations to all samples.

    Args:
        samples: Dictionary mapping sample_id to sample data

    Returns:
        Dictionary with all samples pruned (excludes samples that return None)
    """
    pruned = {}
    for sample_id, sample in samples.items():
        result = prune_sample(sample)
        if result is not None:
            pruned[sample_id] = result
    return pruned

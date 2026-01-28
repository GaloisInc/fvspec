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

from typing import Any

# Fields to remove from the final output
FIELDS_TO_REMOVE = {
    # Add field names here that should be removed from the output
    # Example: "internal_id", "debug_info", etc.
}

# Field renames: old_name -> new_name
FIELD_RENAMES = {
    # Add field renames here
    # Example: "old_field_name": "new_field_name"
}

# Desired field order (fields not listed will appear after these in alphabetical order)
FIELD_ORDER = [
    "sample_id",
    "id",
    "name",
    "repo_id",
    "run_provenance",
    # Core content
    "code",
    "spec",
    "impl",
    "tests",
    # Results
    "success",
    "num_theorems",
    "has_unit_tests",
    # Metadata fields follow
]


def prune_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """Apply pruning transformations to a sample.

    Args:
        sample: Sample dictionary to transform

    Returns:
        Transformed sample dictionary with:
        - Removed fields excluded
        - Fields renamed according to FIELD_RENAMES
        - Fields reordered according to FIELD_ORDER
    """
    # Step 1: Remove fields
    pruned = {k: v for k, v in sample.items() if k not in FIELDS_TO_REMOVE}

    # Step 2: Rename fields
    for old_name, new_name in FIELD_RENAMES.items():
        if old_name in pruned:
            pruned[new_name] = pruned.pop(old_name)

    # Step 3: Reorder fields
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
        Dictionary with all samples pruned
    """
    return {sample_id: prune_sample(sample) for sample_id, sample in samples.items()}

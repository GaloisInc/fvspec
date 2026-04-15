"""Query functions for realpbt2.jsonl dataset.

All data access should go through these functions for consistency and testability.
"""

import json
import logging
import random
from pathlib import Path

from generate.scaffold.dataset.models import Datapoint

logger = logging.getLogger(__name__)

# Maximum number of dependencies allowed per sample before filtering
# Rationale: Samples with >100 dependencies are extreme outliers that:
# 1. Generate excessively large prompts (degraded model performance)
# 2. Take disproportionately long to autoformalize (hurt parallelism)
# 3. Are often synthetic/generated code rather than real-world tests
# 4. Exceed practical limits for meaningful specification generation
MAX_DEPENDENCIES = 100


def load_jsonl(path: Path) -> list[Datapoint]:
    """Parse a JSONL file into a list of Datapoint objects.

    Args:
        path: Path to the .jsonl file

    Returns:
        List of parsed Datapoint objects
    """
    datapoints: list[Datapoint] = []
    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                datapoints.append(Datapoint.model_validate(record))
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Skipping invalid record at line {line_num}: {e}")
    return datapoints


def sample_datapoints(
    datapoints: list[Datapoint],
    n: int,
    ranseed: int | None = 0,
    start_idx: int | None = None,
    end_idx: int | None = None,
) -> list[Datapoint]:
    """Sample n random datapoints, filtering by dependency count.

    When start_idx and/or end_idx are provided, returns a sequential slice
    instead of random sampling.

    Args:
        datapoints: Full list of datapoints to sample from
        n: Number of samples to draw (ignored if start_idx/end_idx provided)
        ranseed: Random seed for reproducibility (default: 0)
        start_idx: Starting index in the ordered dataset (0-indexed, inclusive)
        end_idx: Ending index in the ordered dataset (0-indexed, exclusive)

    Returns:
        List of sampled Datapoint objects
    """
    # Filter by dependency count and sort by id for deterministic ordering
    eligible = [dp for dp in datapoints if len(dp.dependencies) <= MAX_DEPENDENCIES]
    eligible.sort(key=lambda dp: dp.id)

    if not eligible:
        return []

    # Sequential mode: slice by indices if provided
    if start_idx is not None or end_idx is not None:
        return eligible[start_idx:end_idx]

    # Random sampling mode: shuffle and take first n
    rng = random.Random(ranseed)
    ids = list(range(len(eligible)))
    rng.shuffle(ids)
    sample_size = min(n, len(ids))
    selected_indices = ids[:sample_size]
    return [eligible[i] for i in selected_indices]


def load_datapoints_by_id(
    datapoints: list[Datapoint],
    ids: list[int],
) -> dict[int, Datapoint]:
    """Load specific datapoints by their IDs.

    Args:
        datapoints: Full list of datapoints
        ids: List of datapoint IDs to load

    Returns:
        Dictionary mapping datapoint ID to Datapoint object (only IDs that were found)
    """
    id_set = set(ids)
    return {dp.id: dp for dp in datapoints if dp.id in id_set}

"""Query functions for the fvspec-pbt dataset.

All data access should go through these functions for consistency and testability.
Datapoints are loaded from the Hugging Face Hub (``GaloisInc/fvspec-pbt``) by
default, or from a local JSONL file when an existing path is supplied.
"""

import json
import logging
import random
from pathlib import Path

from generate.scaffold.dataset.models import Datapoint

logger = logging.getLogger(__name__)

# Default source dataset on the Hugging Face Hub.
DEFAULT_HF_REPO = "GaloisInc/fvspec-pbt"

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


def load_hf(repo_id: str = DEFAULT_HF_REPO, split: str = "train") -> list[Datapoint]:
    """Load datapoints from a Hugging Face Hub dataset.

    The dataset schema matches the :class:`Datapoint` model field-for-field, so
    each row validates directly.

    Args:
        repo_id: HF dataset repo id (e.g. ``"GaloisInc/fvspec-pbt"``)
        split: Dataset split to load

    Returns:
        List of parsed Datapoint objects
    """
    from datasets import load_dataset

    logger.info(f"Loading datapoints from Hugging Face Hub: {repo_id} ({split})")
    ds = load_dataset(repo_id, split=split)
    datapoints: list[Datapoint] = []
    for idx, record in enumerate(ds):
        try:
            datapoints.append(Datapoint.model_validate(record))
        except ValueError as e:
            logger.warning(f"Skipping invalid record at index {idx}: {e}")
    return datapoints


def load_datapoints(source: str | Path | None = None) -> list[Datapoint]:
    """Load datapoints from a local JSONL file or the Hugging Face Hub.

    If ``source`` points to an existing file it is parsed as JSONL; otherwise
    ``source`` (or the default) is treated as a HF dataset repo id.

    Args:
        source: Local JSONL path, a HF repo id, or None for the default repo.

    Returns:
        List of parsed Datapoint objects
    """
    if source is not None and Path(source).exists():
        return load_jsonl(Path(source))
    return load_hf(str(source) if source else DEFAULT_HF_REPO)


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

"""Dataset loading and stratified sampling for fvspec baselines.

Supports loading from local JSONL files or the quinn-dougherty/fvspec
HuggingFace dataset.
"""

import json
import logging
from pathlib import Path

from inspect_ai.dataset import MemoryDataset, Sample

from baselines.models import FvspecSample
from baselines.prompts import render_user_prompt

logger = logging.getLogger(__name__)

# Equal bucket weights: 1/3 each
BUCKET_RATIOS = {"easy": 1 / 3, "medium": 1 / 3, "hard": 1 / 3}


def bucket_sizes(num_samples: int) -> dict[str, int]:
    """Compute per-bucket sizes from total sample count and ratios.

    Distributes any rounding remainder to the largest bucket (medium).
    """
    raw = {k: int(v * num_samples) for k, v in BUCKET_RATIOS.items()}
    remainder = num_samples - sum(raw.values())
    raw["medium"] += remainder
    return raw


def load_samples_from_jsonl(path: str | Path) -> list[FvspecSample]:
    """Load all samples from a local JSONL file."""
    p = Path(path)
    if not p.is_absolute():
        p = Path(__file__).parents[2] / p
    samples = []
    with p.open() as f:
        for line in f:
            row = json.loads(line)
            samples.append(
                FvspecSample(
                    sample_id=str(row["sample_id"]),
                    spec=row.get("spec") or "",
                    impl=row.get("impl") or "",
                    realpbt_code=row.get("realpbt_code") or "",
                    realpbt_summary=row.get("realpbt_summary"),
                    num_theorems=row.get("num_theorems") or 0,
                    difficulty_subjective_haiku=row.get("difficulty_subjective_haiku"),
                )
            )
    return samples


def load_samples_from_hf() -> list[FvspecSample]:
    """Load all samples from the quinn-dougherty/fvspec HuggingFace dataset."""
    from datasets import load_dataset

    ds = load_dataset("quinn-dougherty/fvspec", split="train")
    samples = []
    for row in ds:
        samples.append(
            FvspecSample(
                sample_id=str(row["sample_id"]),
                spec=row["spec"] or "",
                impl=row["impl"] or "",
                realpbt_code=row["realpbt_code"] or "",
                realpbt_summary=row["realpbt_summary"],
                num_theorems=row["num_theorems"] or 0,
                difficulty_subjective_haiku=row["difficulty_subjective_haiku"],
            )
        )
    return samples


def load_samples(data_source: str = "data/fvspec-mar27.jsonl") -> list[FvspecSample]:
    """Load samples from the configured data source.

    Args:
        data_source: Path to a local JSONL file, or "huggingface" to
            load from quinn-dougherty/fvspec.
    """
    if data_source.lower() == "huggingface":
        return load_samples_from_hf()
    return load_samples_from_jsonl(data_source)


def load_and_sample(
    ranseed: int = 42,
    num_samples: int = 75,
    data_source: str = "data/fvspec-mar27.jsonl",
) -> list[FvspecSample]:
    """Load dataset and apply stratified sampling by difficulty bucket.

    Splits *num_samples* across easy/medium/hard using equal bucket ratios,
    shuffled within each bucket using a fixed random seed.
    """
    import random

    all_samples = load_samples(data_source)
    sizes = bucket_sizes(num_samples)

    # Group by bucket
    buckets: dict[str, list[FvspecSample]] = {"easy": [], "medium": [], "hard": []}
    for sample in all_samples:
        bucket = sample.difficulty_bucket
        if bucket in buckets:
            buckets[bucket].append(sample)

    rng = random.Random(ranseed)

    selected: list[FvspecSample] = []
    for bucket_name, target_size in sizes.items():
        pool = buckets[bucket_name]
        rng.shuffle(pool)

        if len(pool) < target_size:
            logger.warning(
                "Bucket %s has %d samples, wanted %d — taking all",
                bucket_name,
                len(pool),
                target_size,
            )
            selected.extend(pool)
        else:
            selected.extend(pool[:target_size])

    logger.info(
        "Sampled %d total: easy=%d, medium=%d, hard=%d",
        len(selected),
        min(len(buckets["easy"]), sizes["easy"]),
        min(len(buckets["medium"]), sizes["medium"]),
        min(len(buckets["hard"]), sizes["hard"]),
    )
    return selected


def to_inspect_dataset(samples: list[FvspecSample]) -> MemoryDataset:
    """Convert FvspecSamples to an inspect_ai MemoryDataset."""
    inspect_samples = []
    for sample in samples:
        inspect_samples.append(
            Sample(
                id=sample.sample_id,
                input=render_user_prompt(sample),
                metadata={
                    "impl": sample.impl,
                    "spec": sample.spec,
                    "realpbt_code": sample.realpbt_code,
                    "realpbt_summary": sample.realpbt_summary,
                    "num_theorems": sample.num_theorems,
                    "difficulty_bucket": sample.difficulty_bucket,
                    "difficulty_subjective_haiku": sample.difficulty_subjective_haiku,
                },
            )
        )
    return MemoryDataset(samples=inspect_samples)

"""Aggregate inspect_ai eval logs into results.toml for the paper."""

import json
import logging
import re
import zipfile
from datetime import datetime
from pathlib import Path

import tomli_w

from baselines.models import BucketStats, RunStats

logger = logging.getLogger(__name__)


def _read_eval_log(log_path: Path) -> dict:
    """Read an inspect_ai .eval log file (JSON or zipped JSON)."""
    if log_path.suffix == ".zip" or str(log_path).endswith(".eval"):
        # .eval files are zip archives containing a JSON file
        try:
            with zipfile.ZipFile(log_path) as zf:
                names = zf.namelist()
                json_name = next((n for n in names if n.endswith(".json")), names[0])
                with zf.open(json_name) as f:
                    return json.load(f)
        except zipfile.BadZipFile:
            # Try as plain JSON
            return json.loads(log_path.read_text())
    return json.loads(log_path.read_text())


def _extract_model_name(eval_data: dict) -> str:
    """Extract a short model name from eval log metadata."""
    model = eval_data.get("eval", {}).get("model", "unknown")
    # Shorten: "anthropic/claude-sonnet-4-20250514" → "claude-sonnet-4"
    short = model.split("/")[-1]
    # Remove date suffix
    short = re.sub(r"-\d{8}$", "", short)
    return short


def aggregate_logs(log_dir: str = "artifacts") -> dict[str, RunStats]:
    """Aggregate .eval log files into per-model RunStats.

    Args:
        log_dir: Directory containing .eval log files

    Returns:
        Dictionary mapping model name to RunStats
    """
    log_path = Path(log_dir)
    eval_files = list(log_path.glob("**/*.eval"))
    if not eval_files:
        logger.warning("No .eval files found in %s", log_dir)
        return {}

    # Collect per-model results
    model_results: dict[str, dict[str, list[dict]]] = {}

    for eval_file in eval_files:
        try:
            data = _read_eval_log(eval_file)
        except Exception as e:
            logger.warning("Failed to read %s: %s", eval_file, e)
            continue

        model = _extract_model_name(data)
        if model not in model_results:
            model_results[model] = {"easy": [], "medium": [], "hard": []}

        # Extract per-sample results from the eval log
        for sample in data.get("samples", []):
            scores = sample.get("scores", {})
            # inspect_ai stores scorer results under the scorer name
            score_data = scores.get("lake_build_scorer", {})
            if not score_data:
                # Try first available scorer
                score_data = next(iter(scores.values()), {})

            metadata = score_data.get("metadata", {})
            bucket = metadata.get("difficulty_bucket", "unknown")
            proved = metadata.get("proved", False)

            if bucket in model_results[model]:
                model_results[model][bucket].append({"proved": proved})

    # Build RunStats
    stats: dict[str, RunStats] = {}
    for model, buckets in model_results.items():
        run = RunStats(model=model)
        total_proved = 0
        total_n = 0

        for bucket_name in ["easy", "medium", "hard"]:
            results = buckets[bucket_name]
            n = len(results)
            proved = sum(1 for r in results if r["proved"])
            rate = proved / n if n > 0 else 0.0

            bucket_stats = BucketStats(proved=proved, n=n, rate=round(rate, 4))
            setattr(run, bucket_name, bucket_stats)

            total_proved += proved
            total_n += n

        run.total = BucketStats(
            proved=total_proved,
            n=total_n,
            rate=round(total_proved / total_n, 4) if total_n > 0 else 0.0,
        )
        stats[model] = run

    return stats


def write_results_toml(
    stats: dict[str, RunStats],
    output_path: str = "artifacts/results.toml",
    ranseed: int = 42,
    num_samples: int = 1000,
) -> Path:
    """Write aggregated results to TOML for typst consumption.

    Args:
        stats: Per-model RunStats
        output_path: Output file path
        ranseed: Random seed used for sampling

    Returns:
        Path to the written TOML file
    """
    from baselines.dataset import bucket_sizes

    sizes = bucket_sizes(num_samples)
    doc: dict = {
        "meta": {
            "ranseed": ranseed,
            "num_samples": num_samples,
            "timestamp": datetime.now().isoformat(),
            "bucket_sizes": list(sizes.values()),
        },
        "results": {},
    }

    for model_name, run in stats.items():
        model_key = model_name.replace(".", "_").replace("-", "_")
        doc["results"][model_key] = {
            "easy_proved": run.easy.proved,
            "easy_n": run.easy.n,
            "easy_rate": run.easy.rate,
            "medium_proved": run.medium.proved,
            "medium_n": run.medium.n,
            "medium_rate": run.medium.rate,
            "hard_proved": run.hard.proved,
            "hard_n": run.hard.n,
            "hard_rate": run.hard.rate,
            "total_proved": run.total.proved,
            "total_n": run.total.n,
            "total_rate": run.total.rate,
        }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(tomli_w.dumps(doc).encode())
    logger.info("Wrote results to %s", out)
    return out

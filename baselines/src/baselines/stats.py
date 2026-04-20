"""Aggregate inspect_ai eval logs into results TOML/JSON for the paper."""

import json
import logging
import re
import zipfile
from datetime import datetime
from math import comb
from pathlib import Path

import tomli_w

from baselines.models import BucketStats, RunStats

logger = logging.getLogger(__name__)


def _read_eval_log(log_path: Path) -> dict:
    """Read an inspect_ai .eval log file.

    Supports both V1 (single JSON) and V2 (zip with _journal/start.json or
    header.json + samples/*.json).
    Returns a dict with 'eval' header and 'samples' list.
    """
    if log_path.suffix == ".zip" or str(log_path).endswith(".eval"):
        try:
            with zipfile.ZipFile(log_path) as zf:
                names = zf.namelist()

                # V2 format: _journal/start.json or header.json + samples/*.json
                header_file = (
                    "_journal/start.json"
                    if "_journal/start.json" in names
                    else "header.json"
                    if "header.json" in names
                    else None
                )
                if header_file:
                    with zf.open(header_file) as f:
                        data = json.load(f)
                    samples = []
                    for name in names:
                        if name.startswith("samples/") and name.endswith(".json"):
                            with zf.open(name) as f:
                                samples.append(json.load(f))
                    data["samples"] = samples
                    return data

                # V1 format: single JSON file
                json_name = next((n for n in names if n.endswith(".json")), names[0])
                with zf.open(json_name) as f:
                    return json.load(f)
        except zipfile.BadZipFile:
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


def _extract_eval_timestamp(eval_data: dict) -> str | None:
    """Extract the created timestamp from eval log metadata.

    Returns the timestamp in filename-safe format (e.g. '2026-03-27T21-43-46+00-00')
    matching the inspect_ai .eval filename convention.
    """
    created = eval_data.get("eval", {}).get("created")
    if not created:
        return None
    # Convert ISO format colons to hyphens to match .eval filename convention
    return created.replace(":", "-")


def _pass_at_k_unbiased(n: int, c: int, k: int) -> float:
    """Chen et al. unbiased pass@k estimator (arXiv:2107.03374).

    n: total epochs for the sample; c: epochs where the sample passed; k: target k.
    """
    if n - c < k:
        return 1.0
    return 1.0 - comb(n - c, k) / comb(n, k)


def aggregate_logs(
    log_dir: str = "artifacts",
) -> tuple[dict[str, RunStats], str | None]:
    """Aggregate .eval log files into per-model RunStats.

    Args:
        log_dir: Directory containing .eval log files

    Returns:
        Tuple of (model stats dict, eval timestamp in filename-safe format).
        Timestamp comes from the most recent .eval file's created field.
    """
    log_path = Path(log_dir)
    eval_files = list(log_path.glob("**/*.eval"))
    if not eval_files:
        logger.warning("No .eval files found in %s", log_dir)
        return {}, None

    # Collect per-model, per-bucket, per-sample_id attempts across epochs.
    # Shape: model -> bucket -> sample_id -> list of {proved, partial_credit}
    model_results: dict[str, dict[str, dict[str, list[dict]]]] = {}
    eval_timestamps: list[str] = []

    for eval_file in eval_files:
        try:
            data = _read_eval_log(eval_file)
        except Exception as e:
            logger.warning("Failed to read %s: %s", eval_file, e)
            continue

        ts = _extract_eval_timestamp(data)
        if ts:
            eval_timestamps.append(ts)

        model = _extract_model_name(data)
        if model not in model_results:
            model_results[model] = {"easy": {}, "hard": {}}

        for sample in data.get("samples", []):
            scores = sample.get("scores", {})
            score_data = scores.get("lake_build_scorer", {})
            if not score_data:
                score_data = next(iter(scores.values()), {})

            metadata = score_data.get("metadata", {})
            bucket = metadata.get("difficulty_bucket", "unknown")
            proved = bool(metadata.get("proved", False))
            partial_credit = metadata.get("partial_credit", 0.0)
            sample_id = str(sample.get("id", ""))

            if bucket not in model_results[model]:
                continue
            model_results[model][bucket].setdefault(sample_id, []).append(
                {"proved": proved, "partial_credit": partial_credit}
            )

    # Build RunStats with pass@k metrics derived per sample_id.
    stats: dict[str, RunStats] = {}
    for model, buckets in model_results.items():
        run = RunStats(model=model)
        totals = {
            "proved": 0,
            "n": 0,
            "partial_sum": 0.0,
            "pass1_sum": 0.0,
            "passk_sum": 0.0,
            "k": 1,
        }

        for bucket_name in ["easy", "hard"]:
            per_sample = buckets[bucket_name]
            n = len(per_sample)
            # Per-sample k is the number of epochs (attempts) recorded.
            # We take the max across samples in the bucket as the reported k.
            k_bucket = max((len(v) for v in per_sample.values()), default=1)

            proved = 0
            partial_sum = 0.0
            pass1_sum = 0.0
            passk_sum = 0.0
            for attempts in per_sample.values():
                epochs = len(attempts)
                correct = sum(1 for a in attempts if a["proved"])
                # "proved" counter: sample counts as proved if any epoch passed
                proved += 1 if correct > 0 else 0
                # partial credit: take the best attempt
                partial_sum += max((a["partial_credit"] for a in attempts), default=0.0)
                pass1_sum += _pass_at_k_unbiased(epochs, correct, 1)
                passk_sum += _pass_at_k_unbiased(epochs, correct, min(k_bucket, epochs))

            rate = proved / n if n > 0 else 0.0
            partial_avg = partial_sum / n if n > 0 else 0.0
            pass_at_1 = pass1_sum / n if n > 0 else 0.0
            pass_at_k = passk_sum / n if n > 0 else 0.0

            bucket_stats = BucketStats(
                proved=proved,
                n=n,
                rate=round(rate, 4),
                partial_credit_avg=round(partial_avg, 4),
                k=k_bucket,
                pass_at_1=round(pass_at_1, 4),
                pass_at_k=round(pass_at_k, 4),
            )
            setattr(run, bucket_name, bucket_stats)

            totals["proved"] += proved
            totals["n"] += n
            totals["partial_sum"] += partial_sum
            totals["pass1_sum"] += pass1_sum
            totals["passk_sum"] += passk_sum
            totals["k"] = max(totals["k"], k_bucket)

        total_n = totals["n"]
        run.total = BucketStats(
            proved=totals["proved"],
            n=total_n,
            rate=round(totals["proved"] / total_n, 4) if total_n > 0 else 0.0,
            partial_credit_avg=round(totals["partial_sum"] / total_n, 4)
            if total_n > 0
            else 0.0,
            k=totals["k"],
            pass_at_1=round(totals["pass1_sum"] / total_n, 4) if total_n > 0 else 0.0,
            pass_at_k=round(totals["passk_sum"] / total_n, 4) if total_n > 0 else 0.0,
        )
        stats[model] = run

    eval_ts = max(eval_timestamps) if eval_timestamps else None
    return stats, eval_ts


def write_results_toml(
    stats: dict[str, RunStats],
    output_dir: str = "artifacts/results",
    ranseed: int = 42,
    num_samples: int = 75,
    eval_timestamp: str | None = None,
) -> Path:
    """Write aggregated results to TOML for typst consumption.

    Args:
        stats: Per-model RunStats
        output_dir: Base directory for results (timestamped subdir created automatically)
        ranseed: Random seed used for sampling
        num_samples: Total number of samples
        eval_timestamp: Timestamp from the .eval file (filename-safe format).
            If None, falls back to current time.

    Returns:
        Path to the written TOML file
    """
    from baselines.dataset import bucket_sizes

    timestamp = eval_timestamp or datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    results_dir = Path(output_dir) / timestamp
    results_dir.mkdir(parents=True, exist_ok=True)

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
            "easy_partial_credit_avg": run.easy.partial_credit_avg,
            "easy_k": run.easy.k,
            "easy_pass_at_1": run.easy.pass_at_1,
            "easy_pass_at_k": run.easy.pass_at_k,
            "hard_proved": run.hard.proved,
            "hard_n": run.hard.n,
            "hard_rate": run.hard.rate,
            "hard_partial_credit_avg": run.hard.partial_credit_avg,
            "hard_k": run.hard.k,
            "hard_pass_at_1": run.hard.pass_at_1,
            "hard_pass_at_k": run.hard.pass_at_k,
            "total_proved": run.total.proved,
            "total_n": run.total.n,
            "total_rate": run.total.rate,
            "total_partial_credit_avg": run.total.partial_credit_avg,
            "total_k": run.total.k,
            "total_pass_at_1": run.total.pass_at_1,
            "total_pass_at_k": run.total.pass_at_k,
        }

    out = results_dir / "results.toml"
    out.write_bytes(tomli_w.dumps(doc).encode())
    logger.info("Wrote results to %s", out)

    # Also write JSON for convenience
    json_out = results_dir / "results.json"
    json_out.write_text(json.dumps(doc, indent=2))
    logger.info("Wrote results to %s", json_out)

    return out

"""Extract turn counts from .eval zip files and patch qa.json files."""

import json
import zipfile
from collections import Counter
from pathlib import Path

from scripts.postproduction.turncount.models import SubagentTurnCounts, TurnCounts


def count_roles(conversation: list[dict]) -> SubagentTurnCounts:
    """Count assistant turns and tool calls in a conversation."""
    roles = Counter(m.get("role") for m in conversation)
    return SubagentTurnCounts(
        turns=roles.get("assistant", 0),
        tool_calls=roles.get("tool", 0),
    )


def extract_sample_turn_counts(sample_data: dict) -> TurnCounts:
    """Extract turn counts from a single .eval sample entry."""
    store = sample_data.get("store", {})

    impl = count_roles(store.get("impl_conversation", []))
    spec = count_roles(store.get("spec_conversation", []))
    units = count_roles(store.get("units_conversation", []))

    return TurnCounts(
        impl=impl,
        spec=spec,
        units=units,
        total_turns=impl.turns + spec.turns + units.turns,
        total_tool_calls=impl.tool_calls + spec.tool_calls + units.tool_calls,
    )


def sample_id_from_entry(entry_name: str) -> str:
    """Extract sample ID from zip entry name.

    'samples/43231_test_winograd_convolution_epoch_1.json' -> '43231_test_winograd_convolution'
    """
    name = entry_name.removeprefix("samples/").removesuffix("_epoch_1.json")
    return name


def find_eval_files(run_dir: Path) -> list[Path]:
    """Find all .eval files in a run directory."""
    return sorted(run_dir.glob("*.eval"))


def extract_turn_counts_from_eval(eval_path: Path) -> dict[str, TurnCounts]:
    """Extract turn counts for all samples in an .eval zip file.

    Returns a dict mapping sample_id -> TurnCounts.
    """
    results: dict[str, TurnCounts] = {}

    with zipfile.ZipFile(eval_path, "r") as zf:
        for entry in zf.namelist():
            if not entry.startswith("samples/") or not entry.endswith(".json"):
                continue

            sample_id = sample_id_from_entry(entry)
            sample_data = json.loads(zf.read(entry))
            results[sample_id] = extract_sample_turn_counts(sample_data)

    return results


def patch_qa_json(qa_path: Path, turn_counts: TurnCounts) -> bool:
    """Patch a qa.json file with turn count data. Returns True if written."""
    data = json.loads(qa_path.read_text())
    data["turn_counts"] = turn_counts.model_dump()
    qa_path.write_text(json.dumps(data, indent=2) + "\n")
    return True

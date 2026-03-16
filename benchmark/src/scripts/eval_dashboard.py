"""Interactive Streamlit dashboard for exploring .eval benchmark results.

Usage:
    uv run eval-dashboard
"""

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import cast

import streamlit as st

# Constants
DEFAULT_ARTIFACTS_DIR = Path("benchmark/artifacts/runs")
MESSAGES_PER_PAGE = 15


def get_artifacts_dir() -> Path:
    """Get the path to the artifacts directory containing .eval files.

    Tries multiple locations in order:
    1. benchmark/artifacts/runs (from cwd)
    2. ../benchmark/artifacts/runs (from scripts dir)
    3. ../../benchmark/artifacts/runs (from deeper nesting)
    4. Environment variable FVSPEC_ARTIFACTS_DIR

    Returns:
        Path to artifacts directory (may not exist)
    """
    import os

    # Check environment variable first
    env_path = os.getenv("FVSPEC_ARTIFACTS_DIR")
    if env_path:
        return Path(env_path)

    # Try relative paths
    possible_paths = [
        Path("benchmark/artifacts/runs"),
        Path("../benchmark/artifacts/runs"),
        Path("../../benchmark/artifacts/runs"),
        Path.cwd() / "benchmark" / "artifacts" / "runs",
    ]

    for path in possible_paths:
        if path.exists():
            return path

    # Return default if none found
    return DEFAULT_ARTIFACTS_DIR


# ============================================================================
# File Discovery & Loading
# ============================================================================


@st.cache_data(ttl=300)
def discover_eval_files(artifacts_dir: Path) -> list[dict]:
    """Recursively find .eval files and extract basic metadata.

    Args:
        artifacts_dir: Root directory to search for .eval files

    Returns:
        List of dicts with keys: path, filename, timestamp, variant, size_mb, num_samples
    """
    if not artifacts_dir.exists():
        return []

    eval_files = []
    for eval_path in artifacts_dir.rglob("*.eval"):
        try:
            # Extract metadata from filename and path
            filename = eval_path.name
            size_mb = eval_path.stat().st_size / (1024 * 1024)

            # Try to parse timestamp and variant from parent directory name
            # Format: YYYY-MM-DDTHH-MM-SS__variant
            parent = eval_path.parent.name
            parts = parent.split("__")
            timestamp = parts[0] if parts else "Unknown"
            variant = parts[1] if len(parts) > 1 else "Unknown"

            # Quick peek to count samples (optional, may be slow for large files)
            num_samples = 0
            try:
                with zipfile.ZipFile(eval_path, "r") as z:
                    sample_files = [n for n in z.namelist() if n.startswith("samples/")]
                    num_samples = len(sample_files)
            except Exception:
                # If the zip file is corrupt or unreadable, skip sample counting and continue.
                pass

            eval_files.append(
                {
                    "path": eval_path,
                    "filename": filename,
                    "timestamp": timestamp,
                    "variant": variant,
                    "size_mb": size_mb,
                    "num_samples": num_samples,
                }
            )
        except Exception:
            continue

    # Sort by timestamp (newest first)
    eval_files.sort(key=lambda x: x["timestamp"], reverse=True)
    return eval_files


def safe_json_load(zip_file: zipfile.ZipFile, path: str) -> dict | None:
    """Load JSON from zip with error handling.

    Args:
        zip_file: Open ZipFile object
        path: Path within the zip file

    Returns:
        Parsed JSON dict or None on failure
    """
    try:
        content = zip_file.read(path).decode("utf-8")
        data = json.loads(content)
        return data
    except Exception:
        return None


@st.cache_data
def load_eval_file(eval_path: Path) -> dict[str, dict | list | None]:
    """Load and parse .eval ZIP archive.

    Args:
        eval_path: Path to .eval file

    Returns:
        Dict with keys: header, summaries, samples (dict mapping sample_id -> data), errors (list)
    """
    result: dict[str, dict | list | None] = {
        "header": None,
        "summaries": None,
        "samples": {},
        "errors": [],
    }

    try:
        with zipfile.ZipFile(eval_path, "r") as z:
            # Load header
            if "header.json" in z.namelist():
                result["header"] = safe_json_load(z, "header.json")

            # Load summaries
            if "summaries.json" in z.namelist():
                result["summaries"] = safe_json_load(z, "summaries.json")

            # Load all sample files
            sample_files = [n for n in z.namelist() if n.startswith("samples/")]
            for sample_file in sample_files:
                sample_data = safe_json_load(z, sample_file)
                if sample_data:
                    # Use the sample's own id field (which includes test name)
                    # Fall back to extracting from filename if not present
                    sample_id = sample_data.get("id")
                    if not sample_id:
                        # Extract sample ID from filename (e.g., "44448_test_name_epoch_1.json")
                        sample_id_match = re.match(r"samples/(\d+)_", sample_file)
                        if sample_id_match:
                            sample_id = int(sample_id_match.group(1))

                    if sample_id:
                        samples_dict = cast(dict, result["samples"])
                        samples_dict[sample_id] = sample_data

    except Exception as e:
        errors_list = cast(list, result["errors"])
        errors_list.append(f"Error loading eval file: {e}")

    return result


def parse_sample_id_from_filename(filename: str) -> tuple[int, str]:
    """Extract sample ID and test name from sample filename.

    Args:
        filename: Sample filename like "44448_test_name_epoch_1.json"

    Returns:
        Tuple of (sample_id, test_name)
    """
    # Pattern: samples/XXXXX_test_name_epoch_1.json
    match = re.match(r"(?:samples/)?(\d+)_(.*?)(?:_epoch_\d+)?\.json", filename)
    if match:
        return int(match.group(1)), match.group(2)
    return 0, "unknown"


# ============================================================================
# Data Extraction
# ============================================================================


def extract_lean_files(sample: dict) -> dict:
    """Extract Lean code from sample.store.

    Args:
        sample: Sample data dict from .eval file

    Returns:
        Dict with keys: impl_code, spec_code, tests_code (each str | None)
    """
    store = sample.get("store", {})

    return {
        "impl_code": store.get("impl_code"),
        "spec_code": store.get("spec_result", {}).get("lean_code")
        if store.get("spec_result")
        else None,
        "tests_code": store.get("units_result", {}).get("lean_code")
        if store.get("units_result")
        else None,
    }


def extract_compilation_status(sample: dict) -> dict:
    """Extract compilation and validation status.

    Args:
        sample: Sample data dict from .eval file

    Returns:
        Dict with compilation status flags
    """
    store = sample.get("store", {})
    spec_result = store.get("spec_result", {})
    units_result = store.get("units_result", {})

    return {
        "spec_compiles": spec_result.get("compiles", False),
        "spec_has_sorry": spec_result.get("has_sorry", False),
        "spec_has_statements": spec_result.get("has_statements", False),
        "impl_compiles": store.get("impl_result", {}).get("compiles", False),
        "units_test_count": units_result.get("test_count", 0),
        "units_has_tests": units_result.get("has_tests", False),
    }


def extract_metadata_summary(sample: dict) -> dict:
    """Extract key metadata for display.

    Args:
        sample: Sample data dict from .eval file

    Returns:
        Dict with summary metadata
    """
    metadata = sample.get("metadata", {})
    datapoint = metadata.get("datapoint", {})
    output = sample.get("output", {})

    return {
        "sample_id": datapoint.get("id", 0),
        "test_name": datapoint.get("name", "Unknown"),
        "variant": metadata.get("variant", "Unknown"),
        "python_source_file": datapoint.get("source", "Unknown"),
        "success": sample.get("scores", {}).get("success", {}).get("value", "I") == "C",
        "tokens": sample.get("scores", {}).get("token_usage", {}).get("value", 0),
        "time": output.get("time", 0.0) if output else 0.0,
        "model": output.get("model", "Unknown") if output else "Unknown",
    }


def extract_scores(sample: dict) -> dict:
    """Extract all score metrics from sample.scores.

    Args:
        sample: Sample data dict from .eval file

    Returns:
        Dict mapping score name -> score data dict (value, explanation)
    """
    return sample.get("scores", {})


# ============================================================================
# Filtering & Search
# ============================================================================


def get_available_variants(samples: dict) -> list[str]:
    """Extract unique variants from loaded samples.

    Args:
        samples: Dict of sample_id -> sample_data

    Returns:
        Sorted list of unique variant names
    """
    variants = set()
    for sample in samples.values():
        variant = sample.get("metadata", {}).get("variant")
        if variant:
            variants.add(variant)
    return sorted(variants)


def apply_filters(samples: dict, filters: dict) -> dict:
    """Apply user-selected filters to sample dict.

    Args:
        samples: Dict of sample_id -> sample_data
        filters: Dict with keys: variant, success_only, has_unit_tests, search_query

    Returns:
        Filtered dict of samples
    """
    filtered = {}

    for sample_id, sample in samples.items():
        try:
            # Extract metadata for filtering
            metadata_summary = extract_metadata_summary(sample)
            store = sample.get("store", {})

            # Variant filter (only apply if variant is specified and not "All")
            if filters.get("variant"):
                if metadata_summary["variant"] != filters["variant"]:
                    continue

            # Success filter
            if filters.get("success_only"):
                if not metadata_summary["success"]:
                    continue

            # Unit tests filter
            if filters.get("has_unit_tests"):
                units_result = store.get("units_result", {})
                if not units_result.get("has_tests", False):
                    continue

            # Search query (test name or sample ID)
            if filters.get("search_query"):
                query = filters["search_query"].lower()
                test_name = metadata_summary["test_name"].lower()
                sample_id_str = str(metadata_summary["sample_id"])
                if query not in test_name and query not in sample_id_str:
                    continue

            filtered[sample_id] = sample
        except Exception:
            # Skip samples that cause errors during filtering
            continue

    return filtered


# ============================================================================
# UI Rendering Components
# ============================================================================


def render_eval_file_selector(eval_files: list[dict]) -> Path | None:
    """Render eval file selector in sidebar.

    Args:
        eval_files: List of eval file metadata dicts

    Returns:
        Selected file path or None
    """
    if not eval_files:
        st.sidebar.warning("No .eval files found")
        return None

    # Format options for selectbox
    options = {
        f"{f['timestamp']} | {f['variant']} ({f['num_samples']} samples, {f['size_mb']:.1f}MB)": f[
            "path"
        ]
        for f in eval_files
    }

    selected = st.sidebar.selectbox(
        "Select .eval file:",
        options=list(options.keys()),
        key="eval_file_selector",
    )

    return options.get(selected) if selected else None


def render_sample_list_sidebar(
    samples: dict, current_sample_id: int | None
) -> int | None:
    """Render filterable list of samples in sidebar.

    Args:
        samples: Dict of sample_id -> sample_data
        current_sample_id: Currently selected sample ID

    Returns:
        Selected sample_id or None
    """
    if not samples:
        st.sidebar.info("No samples match current filters")
        return None

    st.sidebar.subheader(f"Samples ({len(samples)})")

    # Create list of options and sort by numeric ID if possible
    options = {}

    # Sort samples by extracting numeric part if present
    def get_sort_key(sample_id):
        if isinstance(sample_id, int):
            return sample_id
        elif isinstance(sample_id, str):
            # Extract numeric prefix (e.g., "35425" from "35425_test_name")
            match = re.match(r"(\d+)", str(sample_id))
            return int(match.group(1)) if match else sample_id
        return sample_id

    sorted_sample_ids = sorted(samples.keys(), key=get_sort_key)

    for sample_id in sorted_sample_ids:
        metadata = extract_metadata_summary(samples[sample_id])
        success_icon = "✓" if metadata["success"] else "✗"
        # Display just the numeric ID and test name for clarity
        display_id = metadata["sample_id"] if metadata["sample_id"] else sample_id
        label = f"{success_icon} {display_id}: {metadata['test_name']}"
        options[label] = sample_id

    # Find index of current sample
    current_index = 0
    if current_sample_id and current_sample_id in samples:
        try:
            current_index = sorted_sample_ids.index(current_sample_id)
        except ValueError:
            current_index = 0

    selected = st.sidebar.selectbox(
        "Select sample:",
        options=list(options.keys()),
        index=current_index,
        key="sample_selector",
    )

    return options.get(selected) if selected else None


def render_code_comparison(
    python_code: str, python_deps: list[str], lean_files: dict, compilation_status: dict
):
    """Render side-by-side code comparison.

    Args:
        python_code: Python PBT source code
        python_deps: List of dependency names
        lean_files: Dict with impl_code, spec_code, tests_code
        compilation_status: Dict with compilation status flags
    """
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Python Source")
        st.code(python_code, language="python", line_numbers=True)

        if python_deps:
            with st.expander(f"Dependencies ({len(python_deps)})"):
                for dep in python_deps:
                    st.markdown(f"- `{dep}`")

    with col2:
        st.subheader("Lean Files")

        # Tabs for different Lean files
        lean_tabs = st.tabs(["Spec.lean", "Impl.lean", "Tests.lean"])

        with lean_tabs[0]:
            if lean_files["spec_code"]:
                # Show compilation status
                status_parts = []
                if compilation_status["spec_compiles"]:
                    status_parts.append("✓ Compiles")
                if compilation_status["spec_has_sorry"]:
                    status_parts.append("✓ Has sorry")
                if compilation_status["spec_has_statements"]:
                    status_parts.append("✓ Has statements")
                if status_parts:
                    st.caption(" | ".join(status_parts))

                st.code(lean_files["spec_code"], language="lean", line_numbers=True)

        with lean_tabs[1]:
            if lean_files["impl_code"]:
                if compilation_status["impl_compiles"]:
                    st.caption("✓ Compiles")
                st.code(lean_files["impl_code"], language="lean", line_numbers=True)

        with lean_tabs[2]:
            if lean_files["tests_code"]:
                if compilation_status["units_has_tests"]:
                    st.caption(f"✓ {compilation_status['units_test_count']} tests")
                st.code(lean_files["tests_code"], language="lean", line_numbers=True)


def render_metadata_panel(metadata: dict, compilation_status: dict, scores: dict):
    """Render metadata in organized sections with metrics.

    Args:
        metadata: Metadata summary dict
        compilation_status: Compilation status dict
        scores: Scores dict
    """
    # Key metrics (5-column layout)
    st.subheader("Key Metrics")
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Success", "✓" if metadata["success"] else "✗")
    with col2:
        st.metric("Tokens", f"{metadata['tokens']:,}")
    with col3:
        st.metric("Time (s)", f"{metadata['time']:.2f}")
    with col4:
        num_theorems = scores.get("num_theorems", {}).get("value", 0)
        st.metric("Theorems", num_theorems)
    with col5:
        pct = scores.get("percent_plausible", {}).get("value")
        if pct is not None:
            st.metric("Plausible", f"{pct:.0%}")
        else:
            st.metric("Plausible", "N/A")

    st.divider()

    # Source information
    st.subheader("Source Information")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"**Sample ID:** {metadata['sample_id']}")
        st.markdown(f"**Test Name:** {metadata['test_name']}")
        st.markdown(f"**Variant:** {metadata['variant']}")

    with col2:
        st.markdown(f"**Model:** {metadata['model']}")
        st.markdown(f"**Source File:** `{metadata['python_source_file']}`")

    st.divider()

    # Compilation status
    st.subheader("Compilation Status")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Spec.lean:**")
        st.markdown(f"{'✓' if compilation_status['spec_compiles'] else '✗'} Compiles")
        st.markdown(f"{'✓' if compilation_status['spec_has_sorry'] else '✗'} Has sorry")
        st.markdown(
            f"{'✓' if compilation_status['spec_has_statements'] else '✗'} Has statements"
        )

    with col2:
        st.markdown("**Impl.lean:**")
        st.markdown(f"{'✓' if compilation_status['impl_compiles'] else '✗'} Compiles")

    with col3:
        st.markdown("**Tests.lean:**")
        st.markdown(
            f"{'✓' if compilation_status['units_has_tests'] else '✗'} Has tests"
        )
        if compilation_status["units_has_tests"]:
            st.markdown(f"Test count: {compilation_status['units_test_count']}")

    st.divider()

    # Scores breakdown (expandable)
    with st.expander("Scores Breakdown"):
        if scores:
            for score_name, score_data in scores.items():
                value = score_data.get("value", "N/A")
                explanation = score_data.get("explanation", "")

                # Format value based on type
                if isinstance(value, float):
                    value_str = f"{value:.3f}"
                else:
                    value_str = str(value)

                st.markdown(f"**{score_name}:** {value_str}")
                if explanation:
                    st.caption(explanation)
                st.divider()


def extract_conversations_from_store(sample: dict) -> dict[str, list[dict]]:
    """Extract conversations from the store object.

    The three-agent orchestration stores conversations separately for each agent.
    The impl-agent may fork into multiple copies, each with its own conversation.

    Args:
        sample: Sample dict containing store object

    Returns:
        Dict mapping agent name to list of messages:
        {
            "impl_0": [...],
            "impl_1": [...],
            "spec": [...],
            "units": [...]
        }
    """
    store = sample.get("store", {})
    conversations = {}

    # Extract implementation agent conversations (may be multiple due to forking)
    # Check for both single conversation and indexed conversations
    if "impl_conversation" in store:
        impl_conv = store.get("impl_conversation", [])
        if impl_conv:
            conversations["impl"] = impl_conv

    # Check for numbered impl conversations (impl_conversation_0, impl_conversation_1, etc.)
    impl_idx = 0
    while f"impl_conversation_{impl_idx}" in store:
        impl_conv = store.get(f"impl_conversation_{impl_idx}", [])
        if impl_conv:
            conversations[f"impl_{impl_idx}"] = impl_conv
        impl_idx += 1

    # Extract specification agent conversation
    spec_conv = store.get("spec_conversation", [])
    if spec_conv:
        conversations["spec"] = spec_conv

    # Extract units agent conversation
    units_conv = store.get("units_conversation", [])
    if units_conv:
        conversations["units"] = units_conv

    return conversations


def render_conversation_history(messages: list[dict]):
    """Render conversation with collapsible messages, role badges, code highlighting.

    Args:
        messages: List of message dicts from sample
    """
    if not messages:
        return

    st.subheader(f"Conversation ({len(messages)} messages)")

    # Pagination controls
    messages_per_page = MESSAGES_PER_PAGE
    num_pages = (len(messages) + messages_per_page - 1) // messages_per_page

    if num_pages > 1:
        page = st.number_input(
            f"Page (1-{num_pages}):",
            min_value=1,
            max_value=num_pages,
            value=1,
            step=1,
        )
    else:
        page = 1

    start_idx = (page - 1) * messages_per_page
    end_idx = min(start_idx + messages_per_page, len(messages))
    page_messages = messages[start_idx:end_idx]

    # Render messages
    for i, msg in enumerate(page_messages, start=start_idx + 1):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        source = msg.get("source", "")

        # Role badge styling
        role_colors = {
            "system": "🔧",
            "user": "👤",
            "assistant": "🤖",
            "tool": "🔨",
        }
        role_icon = role_colors.get(role, "❓")

        # Create a preview of the content for the expander title
        content_preview = ""
        if isinstance(content, str) and content.strip():
            # Get first 60 chars of content as preview
            preview_text = content.strip().replace("\n", " ")[:60]
            if len(content) > 60:
                preview_text += "..."
            content_preview = f" - {preview_text}"

        # Build title with source only if it exists
        source_text = f"[{source}]" if source else ""

        with st.expander(
            f"{role_icon} #{i}: {role} {source_text}{content_preview}", expanded=False
        ):
            # Check if content contains code blocks
            if isinstance(content, str):
                # Simple markdown rendering
                # Look for <code> tags and render them separately
                code_pattern = r"<code>(.*?)</code>"
                parts = re.split(code_pattern, content, flags=re.DOTALL)

                for j, part in enumerate(parts):
                    if j % 2 == 0:
                        # Regular text
                        if part.strip():
                            st.markdown(part)
                    else:
                        # Code block
                        # Try to detect language
                        if "namespace" in part or "theorem" in part or "def " in part:
                            lang = "lean"
                        elif "def " in part or "import " in part:
                            lang = "python"
                        else:
                            lang = None
                        st.code(part, language=lang, line_numbers=True)
            elif isinstance(content, list):
                # Content is a list (tool calls, etc.)
                st.json(content)
            else:
                st.json(msg)


# ============================================================================
# Bookmarks & History
# ============================================================================


def load_bookmarks() -> list[tuple]:
    """Load bookmarked samples from session state."""
    if "bookmarks" not in st.session_state:
        st.session_state.bookmarks = []
    return st.session_state.bookmarks


def save_bookmark(eval_path: Path, sample_id: int):
    """Save a sample to bookmarks."""
    bookmarks = load_bookmarks()
    bookmark = (str(eval_path), sample_id)
    if bookmark not in bookmarks:
        bookmarks.append(bookmark)
        st.session_state.bookmarks = bookmarks


def remove_bookmark(eval_path: Path, sample_id: int):
    """Remove a sample from bookmarks."""
    bookmarks = load_bookmarks()
    bookmark = (str(eval_path), sample_id)
    if bookmark in bookmarks:
        bookmarks.remove(bookmark)
        st.session_state.bookmarks = bookmarks


def load_history() -> list[tuple]:
    """Load viewing history from session state."""
    if "history" not in st.session_state:
        st.session_state.history = []
    return st.session_state.history


def add_to_history(eval_path: Path, sample_id: int):
    """Add a sample to viewing history."""
    history = load_history()
    entry = (str(eval_path), sample_id)
    # Remove if already exists
    if entry in history:
        history.remove(entry)
    # Add to front
    history.insert(0, entry)
    # Keep only last 20
    st.session_state.history = history[:20]


def format_bookmark_label(eval_path_str: str, sample_id: int) -> str:
    """Format a concise label for bookmark/history entries.

    Args:
        eval_path_str: Path to the .eval file
        sample_id: Sample ID

    Returns:
        Formatted label like "12345 | 11-10_15:18 | ctrl-func"
    """
    try:
        eval_path = Path(eval_path_str)
        parent = eval_path.parent.name

        # Parse timestamp and variant from parent directory
        # Format: YYYY-MM-DDTHH-MM-SS__<additional>__<variant>
        parts = parent.split("__")

        # Extract short timestamp (MM-DD_HH:MM)
        timestamp_str = "unknown"
        if parts:
            full_timestamp = parts[0]  # e.g., "2025-11-10T15-18-13"
            if "T" in full_timestamp:
                date_part, time_part = full_timestamp.split("T")
                # Extract MM-DD from YYYY-MM-DD
                date_components = date_part.split("-")
                if len(date_components) >= 3:
                    month_day = f"{date_components[1]}-{date_components[2]}"
                else:
                    month_day = date_part[-5:]  # fallback

                # Extract HH:MM from HH-MM-SS
                time_components = time_part.split("-")
                if len(time_components) >= 2:
                    hour_min = f"{time_components[0]}:{time_components[1]}"
                else:
                    hour_min = time_part[:5]  # fallback

                timestamp_str = f"{month_day}_{hour_min}"

        # Extract variant (last part)
        variant_str = "unknown"
        if len(parts) >= 2:
            variant_full = parts[-1]  # e.g., "control-functional"
            # Abbreviate common variants
            variant_map = {
                "control-functional": "ctrl-func",
                "terse-functional": "terse-func",
                "control-mvcgen": "ctrl-mvc",
                "terse-mvcgen": "terse-mvc",
            }
            variant_str = variant_map.get(
                variant_full, variant_full[:10]
            )  # truncate if unknown

        return f"{sample_id} | {timestamp_str} | {variant_str}"
    except Exception:
        # Fallback if parsing fails
        return f"Sample {sample_id}"


# ============================================================================
# Main App
# ============================================================================


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Eval Dashboard - fvspec",
        page_icon="📊",
        layout="wide",
    )

    st.title("📊 Eval Dashboard - fvspec")
    st.markdown("Interactive viewer for .eval benchmark results")

    # Initialize session state
    if "current_eval_path" not in st.session_state:
        st.session_state.current_eval_path = None
    if "current_sample_id" not in st.session_state:
        st.session_state.current_sample_id = None

    # Get artifacts directory
    artifacts_dir = get_artifacts_dir()

    # Sidebar
    with st.sidebar:
        st.header("Eval File")

        # Artifacts directory info
        st.caption(f"Searching: {artifacts_dir}")

        if not artifacts_dir.exists():
            return

        # Discover and select eval files
        eval_files = discover_eval_files(artifacts_dir)
        selected_eval_path = render_eval_file_selector(eval_files)

        if selected_eval_path != st.session_state.current_eval_path:
            st.session_state.current_eval_path = selected_eval_path
            st.session_state.current_sample_id = None
            st.rerun()

        st.divider()

        # Filters
        st.header("Filters")

        # Load eval data for filtering
        eval_data = None
        if st.session_state.current_eval_path:
            eval_data = load_eval_file(st.session_state.current_eval_path)

        variants = ["All"]
        if eval_data:
            variants.extend(get_available_variants(eval_data["samples"]))

        filter_variant = st.selectbox("Variant:", variants, key="filter_variant")
        filter_success = st.checkbox("Success only", key="filter_success")
        filter_unit_tests = st.checkbox("Has unit tests", key="filter_unit_tests")
        search_query = st.text_input(
            "Search:", key="search_query", placeholder="Test name or sample ID"
        )

        # Apply filters
        filters = {
            "variant": filter_variant if filter_variant != "All" else None,
            "success_only": filter_success,
            "has_unit_tests": filter_unit_tests,
            "search_query": search_query if search_query else None,
        }

        filtered_samples = {}
        if eval_data and eval_data.get("samples"):
            filtered_samples = apply_filters(eval_data["samples"], filters)
            # Debug info
            if not filtered_samples and eval_data["samples"]:
                st.sidebar.caption(
                    f"⚠️ {len(eval_data['samples'])} samples loaded, 0 after filtering"
                )

        st.divider()

        # Sample list
        selected_sample_id = render_sample_list_sidebar(
            filtered_samples, st.session_state.current_sample_id
        )

        if selected_sample_id != st.session_state.current_sample_id:
            st.session_state.current_sample_id = selected_sample_id
            if st.session_state.current_eval_path and selected_sample_id is not None:
                add_to_history(st.session_state.current_eval_path, selected_sample_id)
            st.rerun()

        st.divider()

        # Bookmarks
        st.header("⭐ Bookmarks")
        bookmarks = load_bookmarks()
        if bookmarks:
            for eval_path_str, sample_id in bookmarks[:5]:  # Show first 5
                label = format_bookmark_label(eval_path_str, sample_id)
                # Use eval_path_str hash to ensure unique keys even with same sample_id
                button_key = f"bookmark_{sample_id}_{hash(eval_path_str)}"
                if st.button(label, key=button_key):
                    st.session_state.current_eval_path = Path(eval_path_str)
                    st.session_state.current_sample_id = sample_id
                    st.rerun()

        st.divider()

        # History
        st.header("📜 History")
        history = load_history()
        if history:
            for eval_path_str, sample_id in history[:5]:  # Show first 5
                label = format_bookmark_label(eval_path_str, sample_id)
                # Use eval_path_str hash to ensure unique keys even with same sample_id
                button_key = f"history_{sample_id}_{hash(eval_path_str)}"
                if st.button(label, key=button_key):
                    st.session_state.current_eval_path = Path(eval_path_str)
                    st.session_state.current_sample_id = sample_id
                    st.rerun()

        st.divider()

        # Cache management
        if st.button(
            "🔄 Clear Cache",
            key="clear_cache",
            help="Clear cached eval files and reload",
        ):
            st.cache_data.clear()
            st.rerun()

    # Main content area
    if not st.session_state.current_eval_path:
        return

    if not st.session_state.current_sample_id:
        return

    # Load sample data
    eval_data = load_eval_file(st.session_state.current_eval_path)

    sample = eval_data["samples"].get(st.session_state.current_sample_id)

    if not sample:
        return

    # Extract data for rendering
    metadata = extract_metadata_summary(sample)
    lean_files = extract_lean_files(sample)
    compilation_status = extract_compilation_status(sample)
    scores = extract_scores(sample)

    # Sample header with bookmark button
    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
    with col1:
        st.metric("Sample ID", metadata["sample_id"])
    with col2:
        st.metric(
            "Test Name",
            metadata["test_name"][:20] + "..."
            if len(metadata["test_name"]) > 20
            else metadata["test_name"],
        )
    with col3:
        st.metric("Variant", metadata["variant"])
    with col4:
        st.metric("Success", "✓" if metadata["success"] else "✗")
    with col5:
        # Bookmark button
        is_bookmarked = (
            str(st.session_state.current_eval_path),
            metadata["sample_id"],
        ) in load_bookmarks()
        if is_bookmarked:
            if st.button("⭐", help="Remove bookmark"):
                remove_bookmark(
                    st.session_state.current_eval_path, metadata["sample_id"]
                )
                st.rerun()
        else:
            if st.button("☆", help="Add bookmark"):
                save_bookmark(st.session_state.current_eval_path, metadata["sample_id"])
                st.rerun()

    st.markdown("---")

    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📝 Code", "📊 Metadata", "💬 Conversation"])

    with tab1:
        python_code = sample.get("metadata", {}).get("datapoint", {}).get("code", "")
        python_deps = (
            sample.get("metadata", {}).get("datapoint", {}).get("dep_names", [])
        )
        render_code_comparison(python_code, python_deps, lean_files, compilation_status)

    with tab2:
        render_metadata_panel(metadata, compilation_status, scores)

    with tab3:
        # Extract conversations from store (three-agent orchestration)
        agent_conversations = extract_conversations_from_store(sample)

        if agent_conversations:
            # Display conversations in tabs for each agent
            agent_names = list(agent_conversations.keys())

            # Format tab labels with better styling for impl forks
            tab_labels = []
            for name in agent_names:
                if name.startswith("impl_"):
                    # Extract fork number for impl agents
                    fork_num = name.split("_")[-1]
                    if fork_num.isdigit():
                        tab_labels.append(f"🔧 IMPL (Fork {fork_num})")
                    else:
                        tab_labels.append(f"🔧 {name.upper()}")
                elif name == "spec":
                    tab_labels.append("📋 SPEC")
                elif name == "units":
                    tab_labels.append("🧪 UNITS")
                else:
                    tab_labels.append(f"🤖 {name.upper()}")

            agent_tabs = st.tabs(tab_labels)

            for i, agent_name in enumerate(agent_names):
                with agent_tabs[i]:
                    messages = agent_conversations[agent_name]
                    render_conversation_history(messages)
        else:
            # Fallback to top-level messages if no store conversations found
            messages = sample.get("messages", [])
            render_conversation_history(messages)


def cli():
    """CLI entry point that launches streamlit."""
    script_path = Path(__file__).resolve()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(script_path),
            "--server.headless",
            "true",
        ]
    )


if __name__ == "__main__":
    main()

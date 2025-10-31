"""Interactive Streamlit app for exploring the fvspec dataset.

Usage:
    uv run data-explorer
"""

import json
import random
import subprocess
import sys
from pathlib import Path

import streamlit as st

from generate.scaffold.dataset import Datapoint
from generate.scaffold.dataset.connection import get_session
from generate.scaffold.dataset.queries import (
    count_total_datapoints,
)
from generate.scaffold.dataset.queries import (
    load_datapoints_by_id as _db_load_by_id,
)
from generate.scaffold.dataset.queries import (
    sample_datapoints as _db_sample,
)


def get_data_path() -> Path:
    """Get the path to the pbts_full.db database file."""
    # Try to find the data file relative to the project root
    possible_paths = [
        Path(__file__).parent.parent.parent.parent / "data" / "pbts_full.db",
        Path.cwd() / "benchmark" / "data" / "pbts_full.db",
        Path.cwd() / "data" / "pbts_full.db",
    ]
    for path in possible_paths:
        if path.exists():
            return path

    # If not found, return default path with helpful error
    return Path(__file__).parent.parent.parent.parent / "data" / "pbts_full.db"


def load_random_sample(
    data_path: Path,
    seed: int | None = None,
    min_deps: int | None = None,
    max_deps: int | None = None,
) -> Datapoint | None:
    """Load a single random sample from the dataset with optional filtering."""
    if not data_path.exists():
        st.error(f"Data file not found: {data_path}")
        st.info("Expected location: benchmark/data/pbts_full.db")
        return None

    try:
        # Try to find a sample matching the filter (up to 50 attempts)
        max_attempts = 50
        for _ in range(max_attempts):
            with get_session(data_path) as session:
                samples = _db_sample(session, n=1, ranseed=seed)

            if not samples:
                return None

            sample = samples[0]
            num_deps = len(sample.get_deps())

            # Check if it matches the filter
            if min_deps is not None and num_deps < min_deps:
                seed = random.randint(0, 1_000_000) if seed is not None else None
                continue
            if max_deps is not None and num_deps > max_deps:
                seed = random.randint(0, 1_000_000) if seed is not None else None
                continue

            return sample

        st.warning(
            f"Could not find sample matching filter after {max_attempts} attempts. Try broader criteria."
        )
        return None
    except Exception as e:
        st.error(f"Error loading sample: {e}")
        return None


def load_sample_by_id(data_path: Path, sample_id: int) -> Datapoint | None:
    """Load a specific sample by ID."""
    try:
        with get_session(data_path) as session:
            result = _db_load_by_id(session, [sample_id])
        return result.get(sample_id)
    except Exception as e:
        st.error(f"Error loading sample {sample_id}: {e}")
        return None


def calculate_stats(
    data_path: Path, sample_size: int = 1000
) -> dict[str, float] | None:
    """Calculate dataset statistics (cached in session state)."""
    if not data_path.exists():
        return None

    try:
        # Sample random points to estimate statistics
        with get_session(data_path) as session:
            total_count = count_total_datapoints(session)
            samples = _db_sample(session, n=sample_size, ranseed=42)

        if not samples:
            return None

        dep_counts = [len(s.get_deps()) for s in samples]
        pbt_lengths = [len(s.code) for s in samples]

        return {
            "avg_deps": sum(dep_counts) / len(dep_counts),
            "median_deps": sorted(dep_counts)[len(dep_counts) // 2],
            "max_deps": max(dep_counts),
            "min_deps": min(dep_counts),
            "avg_pbt_chars": sum(pbt_lengths) / len(pbt_lengths),
            "total_lines": total_count,
            "sample_size": sample_size,
        }
    except Exception as e:
        st.error(f"Error calculating stats: {e}")
        return None


def load_bookmarks() -> list[int]:
    """Load bookmarked sample IDs from local storage (session state)."""
    if "bookmarks" not in st.session_state:
        st.session_state.bookmarks = []
    return st.session_state.bookmarks


def save_bookmark(sample_id: int):
    """Save a sample ID to bookmarks."""
    bookmarks = load_bookmarks()
    if sample_id not in bookmarks:
        bookmarks.append(sample_id)
        st.session_state.bookmarks = bookmarks


def remove_bookmark(sample_id: int):
    """Remove a sample ID from bookmarks."""
    bookmarks = load_bookmarks()
    if sample_id in bookmarks:
        bookmarks.remove(sample_id)
        st.session_state.bookmarks = bookmarks


def load_history() -> list[int]:
    """Load viewing history from session state."""
    if "history" not in st.session_state:
        st.session_state.history = []
    return st.session_state.history


def add_to_history(sample_id: int):
    """Add a sample ID to viewing history."""
    history = load_history()
    # Remove if already exists to avoid duplicates
    if sample_id in history:
        history.remove(sample_id)
    # Add to front
    history.insert(0, sample_id)
    # Keep only last 20
    st.session_state.history = history[:20]


def main():
    """Main Streamlit app."""
    st.set_page_config(page_title="FVSpec Data Explorer", page_icon="🔍", layout="wide")

    st.title("🔍 FVSpec Dataset Explorer")
    st.markdown("Interactive viewer for property-based test samples")

    # Initialize session state
    if "current_sample" not in st.session_state:
        st.session_state.current_sample = None
    if "seed" not in st.session_state:
        st.session_state.seed = random.randint(0, 1_000_000)
    if "stats" not in st.session_state:
        st.session_state.stats = None

    data_path = get_data_path()

    # Sidebar controls
    with st.sidebar:
        st.header("Controls")

        # Search by ID (#1)
        st.subheader("🔍 Search by ID")
        search_id = st.number_input(
            "Enter Sample ID",
            min_value=0,
            step=1,
            value=0,
            key="search_id_input",
        )
        if st.button("Load by ID", width="stretch"):
            sample = load_sample_by_id(data_path, search_id)
            if sample:
                st.session_state.current_sample = sample
                add_to_history(sample.id)
                st.rerun()
            else:
                st.error(f"Sample ID {search_id} not found")

        st.divider()

        # Filter controls (#2)
        st.subheader("🎲 Random Sample")
        with st.expander("Filter Options"):
            enable_filter = st.checkbox("Enable dependency filter", value=False)
            if enable_filter:
                min_deps = st.number_input(
                    "Min dependencies", min_value=0, value=0, step=1
                )
                max_deps = st.number_input(
                    "Max dependencies", min_value=0, value=100, step=1
                )
            else:
                min_deps = None
                max_deps = None

        if st.button("🎲 Load Random Sample", type="primary", width="stretch"):
            st.session_state.seed = random.randint(0, 1_000_000)
            sample = load_random_sample(
                data_path, st.session_state.seed, min_deps, max_deps
            )
            if sample:
                st.session_state.current_sample = sample
                add_to_history(sample.id)
                st.rerun()

        st.divider()

        # History (#8)
        st.subheader("📜 History")
        history = load_history()
        if history:
            selected_history = st.selectbox(
                "Recent samples:",
                options=history,
                format_func=lambda x: f"ID: {x}",
                key="history_selector",
            )
            if st.button("Load from History", width="stretch"):
                sample = load_sample_by_id(data_path, selected_history)
                if sample:
                    st.session_state.current_sample = sample
                    st.rerun()
        else:
            st.info("No history yet")

        st.divider()

        # Bookmarks (#9)
        st.subheader("⭐ Bookmarks")
        bookmarks = load_bookmarks()
        if bookmarks:
            selected_bookmark = st.selectbox(
                "Saved samples:",
                options=bookmarks,
                format_func=lambda x: f"ID: {x}",
                key="bookmark_selector",
            )
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Load", width="stretch"):
                    sample = load_sample_by_id(data_path, selected_bookmark)
                    if sample:
                        st.session_state.current_sample = sample
                        add_to_history(sample.id)
                        st.rerun()
            with col2:
                if st.button("Remove", width="stretch"):
                    remove_bookmark(selected_bookmark)
                    st.rerun()
        else:
            st.info("No bookmarks yet")

        st.divider()

        # Stats (#3)
        st.subheader("📊 Dataset Stats")
        stats_sample_size = 1000
        if st.button("Calculate Stats", width="stretch"):
            with st.spinner(f"Sampling {stats_sample_size} datapoints..."):
                st.session_state.stats = calculate_stats(data_path, stats_sample_size)
            st.rerun()

        if st.session_state.stats:
            stats = st.session_state.stats
            st.caption(f"(estimated from n={stats['sample_size']} samples)")
            st.metric("Total Samples", f"{stats['total_lines']:,}")
            st.metric("Avg Dependencies", f"{stats['avg_deps']:.1f}")
            st.metric("Median Dependencies", f"{stats['median_deps']:.0f}")
            st.metric("Dep Range", f"{stats['min_deps']:.0f} - {stats['max_deps']:.0f}")
            st.metric("Avg PBT Length", f"{stats['avg_pbt_chars']:.0f} chars")

        st.divider()

        # Data file info
        st.subheader("📁 Data Location")
        st.code(str(data_path), language=None)

        if data_path.exists():
            size_gb = data_path.stat().st_size / (1024**3)
            st.metric("File Size", f"{size_gb:.1f} GB")
        else:
            st.warning("Data file not found")

    # Main content area
    sample = st.session_state.current_sample

    if sample is None:
        st.info("👈 Use the sidebar to load a sample!")
        st.markdown("""
        ### About This Tool

        This interactive viewer lets you explore the fvspec dataset:
        - **Search by ID**: Jump to a specific sample
        - **Random sampling**: With optional dependency count filters
        - **Dataset stats**: Calculate distribution statistics
        - **History**: Track recently viewed samples
        - **Bookmarks**: Save interesting samples for later

        **Requirements:**
        - Dataset file: `benchmark/data/pbts_full.db`
        """)
        return

    # Display sample information with bookmark button
    col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
    with col1:
        st.metric("Sample ID", sample.id)
    with col2:
        st.metric("Repo ID", sample.repo_id)
    with col3:
        st.metric("# Dependencies", len(sample.get_deps()))
    with col4:
        st.metric("# Dep Names", len(sample.get_dep_names()))
    with col5:
        # Bookmark button
        is_bookmarked = sample.id in load_bookmarks()
        if is_bookmarked:
            if st.button("⭐", help="Remove bookmark"):
                remove_bookmark(sample.id)
                st.rerun()
        else:
            if st.button("☆", help="Add bookmark"):
                save_bookmark(sample.id)
                st.rerun()

    # Copy buttons (#11)
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("📋 Copy Sample ID", width="stretch"):
            st.code(str(sample.id), language=None)
            st.toast("Sample ID displayed above!")
    with col2:
        if st.button("📋 Copy PBT Code", width="stretch"):
            st.code(sample.code, language="python")
            st.toast("PBT code displayed below!")
    with col3:
        if st.button("📋 Copy All Deps", width="stretch"):
            all_deps = "\n\n# " + "=" * 50 + "\n\n".join(sample.get_deps())
            st.code(all_deps, language="python")
            st.toast("All dependencies displayed below!")
    with col4:
        if st.button("📋 Export JSON", width="stretch"):
            json_str = json.dumps(sample.model_dump(), indent=2)
            st.download_button(
                label="⬇️ Download JSON",
                data=json_str,
                file_name=f"sample_{sample.id}.json",
                mime="application/json",
            )

    st.markdown("---")

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📝 PBT", "🔗 Dependencies", "📄 Source", "📊 Metadata"]
    )

    with tab1:
        st.subheader(f"Property-Based Test: {sample.name}")
        st.code(sample.code, language="python", line_numbers=True)

        # Show source file location if available
        if sample.source_file:
            st.caption(
                f"Source: {sample.source_file} (lines {sample.start_line}-{sample.end_line})"
            )

    with tab2:
        st.subheader("Dependencies")

        deps = sample.get_deps()
        if not deps:
            st.info("No dependencies for this sample")
        else:
            # Dependency selector dropdown
            dep_names = sample.get_dep_names()
            if dep_names and len(dep_names) == len(deps):
                dep_options = {
                    f"{i + 1}. {name}": (i, name) for i, name in enumerate(dep_names)
                }
            else:
                dep_options = {
                    f"Dependency {i + 1}": (i, f"dep_{i + 1}") for i in range(len(deps))
                }

            selected = st.selectbox(
                "Select dependency to view:",
                options=list(dep_options.keys()),
                key="dep_selector",
            )

            if selected:
                idx, name = dep_options[selected]
                st.code(deps[idx], language="python", line_numbers=True)

                # Show stats for this dependency
                dep_lines = deps[idx].count("\n") + 1
                dep_chars = len(deps[idx])
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Lines", dep_lines)
                with col2:
                    st.metric("Characters", dep_chars)

    with tab3:
        st.subheader("Source Code")
        if sample.source:
            st.code(sample.source, language="python", line_numbers=True)
        else:
            st.info("Source code not available in database")

    with tab4:
        st.subheader("Sample Metadata")

        # Basic info
        col1, col2 = st.columns(2)
        with col1:
            if sample.hash:
                st.markdown("**Hash:**")
                st.code(sample.hash, language=None)

            if sample.mode:
                st.markdown(f"**Mode:** {sample.mode}")

            if sample.summaryversion is not None:
                st.markdown(f"**Summary Version:** {sample.summaryversion}")

            if sample.summaryconfidence is not None:
                st.markdown(f"**Summary Confidence:** {sample.summaryconfidence}")

        with col2:
            if sample.original_id is not None:
                st.markdown(f"**Original ID:** {sample.original_id}")

        # Summary
        if sample.summary:
            st.divider()
            st.markdown("**Summary:**")
            st.info(sample.summary)

        # Raw JSON view
        with st.expander("🔍 Raw JSON"):
            st.json(sample.model_dump())


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

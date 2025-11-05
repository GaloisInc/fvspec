"""Interactive Streamlit app for exploring the fvspec dataset.

Usage:
    uv run data-explorer
"""

import ast
import json
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path

import streamlit as st
from sqlmodel import select

from generate.config import DATA_DIR
from generate.scaffold.dataset import Datapoint
from generate.scaffold.dataset.connection import get_session
from generate.scaffold.dataset.models import PBTFunction
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
        DATA_DIR / "pbts_full.db",
        Path.cwd() / "benchmark" / "data" / "pbts_full.db",
        Path.cwd() / "data" / "pbts_full.db",
    ]
    for path in possible_paths:
        if path.exists():
            return path

    # If not found, return default path with helpful error
    return DATA_DIR / "pbts_full.db"


def get_associated_functions(data_path: Path, pbt_id: int) -> list[str]:
    """Get list of functions associated with a PBT from pbt_functions table."""
    try:
        with get_session(data_path) as session:
            statement = select(PBTFunction.function_name).where(
                PBTFunction.pbt_id == pbt_id
            )
            results = session.exec(statement)
            return list(results)
    except Exception as e:
        st.error(f"Error fetching functions: {e}")
        return []


class FunctionCallVisitor(ast.NodeVisitor):
    """AST visitor to extract function calls from Python code."""

    def __init__(self):
        """Initialize the visitor with an empty call list."""
        self.calls: list[dict[str, str | int]] = []

    def visit_Call(self, node: ast.Call):
        """Record function call details."""
        # Extract function name (handles both simple calls and attribute access)
        func_name = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            # For attr.method() calls, try to build full name
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            func_name = ".".join(reversed(parts))

        if func_name:
            self.calls.append(
                {
                    "name": func_name,
                    "line": node.lineno if hasattr(node, "lineno") else 0,
                    "type": "attribute"
                    if isinstance(node.func, ast.Attribute)
                    else "direct",
                }
            )

        self.generic_visit(node)


def analyze_function_calls(code: str) -> dict[str, list | dict | int | str]:
    """Analyze function calls in Python code using AST.

    Returns:
        Dictionary with call counts and detailed call information
    """
    try:
        tree = ast.parse(code)
        visitor = FunctionCallVisitor()
        visitor.visit(tree)

        # Count occurrences
        call_counts = Counter(call["name"] for call in visitor.calls)

        return {
            "calls": visitor.calls,
            "call_counts": dict(call_counts.most_common()),
            "total_calls": len(visitor.calls),
            "unique_functions": len(call_counts),
        }
    except SyntaxError as e:
        return {
            "error": f"Syntax error: {e}",
            "calls": [],
            "call_counts": {},
            "total_calls": 0,
            "unique_functions": 0,
        }


def identify_main_function(
    associated_functions: list[str],
    call_analysis: dict[str, list | dict | int | str],
    dep_names: list[str],
) -> dict[str, list[str] | str | dict]:
    """Apply heuristics to identify which function is likely 'under test' vs dependencies.

    Heuristics:
    1. Most frequently called function is likely the main one
    2. Functions in associated_functions but not in dep_names might be main
    3. Functions called directly (not as attributes) are more likely to be main

    Returns:
        Dictionary with 'likely_main', 'likely_deps', and 'reasoning'
    """
    if not associated_functions:
        return {
            "likely_main": [],
            "likely_deps": [],
            "reasoning": "No associated functions found in pbt_functions table",
        }

    call_counts_raw = call_analysis.get("call_counts", {})
    calls_raw = call_analysis.get("calls", [])

    # Type narrowing for type checker
    assert isinstance(call_counts_raw, dict)  # noqa: S101
    assert isinstance(calls_raw, list)  # noqa: S101
    call_counts: dict[str, int] = call_counts_raw  # type: ignore[assignment]
    calls: list[dict[str, str | int]] = calls_raw  # type: ignore[assignment]

    # Score each associated function
    scores = {}
    for func in associated_functions:
        score = 0
        reasons = []

        # Check if called at all
        call_count = call_counts.get(func, 0)  # type: ignore[union-attr]
        if call_count > 0:
            score += call_count
            reasons.append(f"called {call_count}x")

        # Check if NOT in dep_names (might indicate it's the main function)
        if func not in dep_names:
            score += 5
            reasons.append("not in dep_names")

        # Check for direct calls (not attribute access)
        direct_calls = sum(  # type: ignore[misc]
            1 for c in calls if c["name"] == func and c["type"] == "direct"
        )
        if direct_calls > 0:
            score += 2
            reasons.append(f"{direct_calls} direct call(s)")

        scores[func] = {"score": score, "reasons": reasons}

    # Sort by score
    sorted_funcs = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)

    if not sorted_funcs:
        return {
            "likely_main": [],
            "likely_deps": associated_functions,
            "reasoning": "No functions found in code",
        }

    # Top scorer is likely main, rest are deps
    top_score = sorted_funcs[0][1]["score"]
    likely_main = [func for func, data in sorted_funcs if data["score"] == top_score]
    likely_deps = [func for func, data in sorted_funcs if data["score"] < top_score]

    reasoning = f"Top candidate(s): {likely_main[0]} ({', '.join(sorted_funcs[0][1]['reasons'])})"

    return {
        "likely_main": likely_main,
        "likely_deps": likely_deps,
        "reasoning": reasoning,
        "all_scores": scores,
    }


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
            deps = sample.get_deps()
            num_deps = len(deps)

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
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📝 PBT",
            "🔗 Dependencies",
            "🔍 Function Analysis",
            "📄 Source",
            "📊 Metadata",
        ]
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
        st.subheader("🔍 Function Interdependency Analysis")
        st.markdown(
            """
            This tab helps answer: **Which function is being tested vs which are dependencies?**

            Analysis combines data from:
            - `pbt_functions` table (database-recorded associations)
            - AST-based call analysis of the PBT code
            - Heuristics comparing with `dep_names` field
            """
        )

        # Get associated functions from database
        associated_funcs = get_associated_functions(data_path, sample.id)

        # Analyze function calls in PBT code
        call_analysis = analyze_function_calls(sample.code)

        # Apply heuristics to identify main function
        identification = identify_main_function(
            associated_funcs, call_analysis, sample.get_dep_names()
        )

        # Display results
        st.divider()

        # Overview metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Associated Functions", len(associated_funcs))
        with col2:
            st.metric("Total Calls", call_analysis.get("total_calls", 0))
        with col3:
            st.metric("Unique Called", call_analysis.get("unique_functions", 0))
        with col4:
            st.metric("Dep Names", len(sample.get_dep_names()))

        # Main function identification
        st.divider()
        st.subheader("Identification Results")

        likely_main = identification.get("likely_main", [])
        likely_deps = identification.get("likely_deps", [])
        reasoning = identification.get("reasoning", "")

        if likely_main:
            st.success(f"**Likely Function Under Test:** {', '.join(likely_main)}")
            st.caption(f"Reasoning: {reasoning}")
        else:
            st.warning("Could not identify a clear 'function under test'")

        if likely_deps:
            st.info(f"**Likely Dependencies:** {', '.join(likely_deps)}")

        # Detailed scoring
        with st.expander("📊 Detailed Scoring"):
            all_scores = identification.get("all_scores", {})
            if all_scores and isinstance(all_scores, dict):
                for func, data in sorted(
                    all_scores.items(),
                    key=lambda x: x[1]["score"],
                    reverse=True,  # type: ignore[union-attr]
                ):
                    score = data["score"]
                    reasons = data["reasons"]
                    st.markdown(f"**{func}** (score: {score})")
                    if reasons:
                        for reason in reasons:
                            st.markdown(f"  - {reason}")
                    else:
                        st.markdown("  - No evidence in PBT code")
            else:
                st.info("No functions to score")

        # Associated functions from database
        st.divider()
        st.subheader("Database: Associated Functions")
        if associated_funcs:
            st.markdown("Functions from `pbt_functions` table:")
            call_counts_db_raw = call_analysis.get("call_counts", {})
            assert isinstance(call_counts_db_raw, dict)  # noqa: S101
            call_counts_db: dict[str, int] = call_counts_db_raw  # type: ignore[assignment]
            for func in associated_funcs:
                in_deps = (
                    "✓ in dep_names"
                    if func in sample.get_dep_names()
                    else "✗ NOT in dep_names"
                )
                call_count = call_counts_db.get(func, 0)  # type: ignore[union-attr]
                st.markdown(f"- `{func}` - {in_deps} - Called {call_count}x in PBT")
        else:
            st.info("No associated functions in pbt_functions table for this sample")

        # Call analysis from PBT code
        st.divider()
        st.subheader("PBT Code: Function Calls")

        if "error" in call_analysis:
            st.error(f"Could not parse PBT code: {call_analysis['error']}")
        else:
            call_counts_raw = call_analysis.get("call_counts", {})
            assert isinstance(call_counts_raw, dict)  # noqa: S101
            call_counts: dict[str, int] = call_counts_raw  # type: ignore[assignment]
            if call_counts:
                st.markdown("All function calls found in PBT code:")

                # Show top 20 most called functions
                for func, count in list(call_counts.items())[:20]:  # type: ignore[union-attr]
                    in_assoc = "✓ associated" if func in associated_funcs else ""
                    in_deps = "✓ dep_name" if func in sample.get_dep_names() else ""
                    tags = f"{in_assoc} {in_deps}".strip()
                    if tags:
                        st.markdown(f"- `{func}` called **{count}x** ({tags})")
                    else:
                        st.markdown(f"- `{func}` called **{count}x**")

                if len(call_counts) > 20:  # type: ignore[arg-type]
                    st.caption(f"... and {len(call_counts) - 20} more functions")  # type: ignore[arg-type]
            else:
                st.info("No function calls detected in PBT code")

        # Raw call details
        with st.expander("🔍 Raw Call Details"):
            calls_raw = call_analysis.get("calls", [])
            assert isinstance(calls_raw, list)  # noqa: S101
            calls: list[dict[str, str | int]] = calls_raw  # type: ignore[assignment]
            if calls:
                st.json(
                    [
                        {"function": c["name"], "line": c["line"], "type": c["type"]}  # type: ignore[misc]
                        for c in calls[:50]
                    ]
                )
                if len(calls) > 50:  # type: ignore[arg-type]
                    st.caption(f"Showing first 50 of {len(calls)} calls")  # type: ignore[arg-type]
            else:
                st.info("No calls to display")

    with tab4:
        st.subheader("Source Code")
        if sample.source:
            st.code(sample.source, language="python", line_numbers=True)
        else:
            st.info("Source code not available in database")

    with tab5:
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

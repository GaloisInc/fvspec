"""Interactive Streamlit dashboard for exploring unit test classification results.

Usage:
    uv run unit-test-dashboard
"""

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


def get_data_dir() -> Path:
    """Get the path to the data directory."""
    possible_paths = [
        Path(__file__).parent.parent.parent / "data",
        Path.cwd() / "benchmark" / "data",
        Path.cwd() / "data",
        Path(".") / "data",
    ]
    for path in possible_paths:
        if path.exists():
            return path
    # Return default
    return Path(".") / "data"


def load_summary_csv(data_dir: Path) -> pd.DataFrame | None:
    """Load the summary CSV file."""
    csv_path = data_dir / "unit_test_classification.csv"
    if not csv_path.exists():
        return None
    try:
        df = pd.read_csv(csv_path)
        return df
    except Exception as e:
        st.error(f"Error loading CSV: {e}")
        return None


def load_detailed_jsonl(data_dir: Path) -> list[dict] | None:
    """Load the detailed JSONL file with per-test results."""
    jsonl_path = data_dir / "unit_test_classification_detailed.jsonl"
    if not jsonl_path.exists():
        return None
    try:
        results = []
        with open(jsonl_path) as f:
            for line in f:
                results.append(json.loads(line))
        return results
    except Exception as e:
        st.error(f"Error loading JSONL: {e}")
        return None


def load_metadata(data_dir: Path) -> dict[str, str] | None:
    """Load metadata from the markdown file."""
    md_path = data_dir / "unit_test_classification.md"
    if not md_path.exists():
        return None
    try:
        metadata = {}
        with open(md_path) as f:
            for line in f:
                if line.startswith("Generated:"):
                    metadata["generated"] = line.split(":", 1)[1].strip()
                elif line.startswith("Total tests analyzed:"):
                    metadata["total_tests"] = line.split(":", 1)[1].strip()
                elif line.startswith("Confidence threshold:"):
                    metadata["confidence_threshold"] = line.split(":", 1)[1].strip()
        return metadata
    except Exception:
        return None


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Unit Test Classification Dashboard",
        page_icon="📊",
        layout="wide",
    )

    st.title("📊 Unit Test Classification Dashboard")
    st.markdown("Interactive viewer for unit test classification results")

    data_dir = get_data_dir()

    # Sidebar
    with st.sidebar:
        st.header("Data Location")
        st.code(str(data_dir), language=None)

        st.divider()

        if st.button("🔄 Refresh Data", width="stretch"):
            st.rerun()

        st.divider()

        st.markdown("""
        ### About

        This dashboard visualizes results from:
        ```bash
        uv run classify-unit-tests
        ```

        **Files loaded:**
        - `unit_test_classification.csv` (summary)
        - `unit_test_classification_detailed.jsonl` (per-test)
        """)

    # Load data
    summary_df = load_summary_csv(data_dir)
    detailed_data = load_detailed_jsonl(data_dir)
    metadata = load_metadata(data_dir)

    if summary_df is None:
        st.error("❌ No classification results found")
        st.info(f"Expected file: {data_dir / 'unit_test_classification.csv'}")
        st.markdown("""
        Run the classification script first:
        ```bash
        uv run classify-unit-tests -n 100
        ```
        """)
        return

    # Display metadata if available
    if metadata:
        st.caption(
            f"Generated: {metadata.get('generated', 'Unknown')} | "
            f"Confidence threshold: {metadata.get('confidence_threshold', 'Unknown')}"
        )

    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "📊 Overview",
            "📈 Distribution",
            "🔍 Test Browser",
            "📋 Raw Data",
        ]
    )

    with tab1:
        st.header("Classification Summary")

        # Key metrics
        total_tests = summary_df["Count"].sum()
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Tests", f"{total_tests:,}")

        with col2:
            avg_confidence = (
                summary_df["AvgConfidence"] * summary_df["Count"]
            ).sum() / total_tests
            st.metric("Avg Confidence", f"{avg_confidence:.2f}")

        with col3:
            total_llm = summary_df["LLMUsage"].sum()
            llm_pct = (total_llm / total_tests * 100) if total_tests > 0 else 0
            st.metric("LLM Usage", f"{llm_pct:.1f}%")

        with col4:
            num_categories = (summary_df["Count"] > 0).sum()
            st.metric("Categories Found", num_categories)

        st.divider()

        # Category breakdown table
        st.subheader("Category Breakdown")

        # Add visual indicators
        display_df = summary_df.copy()
        display_df["Percentage"] = display_df["Percentage"].apply(lambda x: f"{x:.1f}%")
        display_df["AvgConfidence"] = display_df["AvgConfidence"].apply(
            lambda x: f"{x:.2f}"
        )
        display_df["LLMUsagePercent"] = display_df["LLMUsagePercent"].apply(
            lambda x: f"{x:.0f}%"
        )

        st.dataframe(
            display_df,
            width="stretch",
            hide_index=True,
            column_config={
                "Category": st.column_config.TextColumn("Category", width="large"),
                "Count": st.column_config.NumberColumn("Count", format="%d"),
                "Percentage": st.column_config.TextColumn("% of Total"),
                "AvgConfidence": st.column_config.TextColumn("Avg Confidence"),
                "LLMUsage": st.column_config.NumberColumn("LLM Usage", format="%d"),
                "LLMUsagePercent": st.column_config.TextColumn("LLM %"),
            },
        )

    with tab2:
        st.header("Distribution Visualizations")

        # Category distribution pie chart
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Tests by Category")
            chart_df = summary_df[summary_df["Count"] > 0].copy()
            st.bar_chart(chart_df.set_index("Category")["Count"])

        with col2:
            st.subheader("LLM Usage by Category")
            chart_df = summary_df[summary_df["Count"] > 0].copy()
            st.bar_chart(chart_df.set_index("Category")["LLMUsagePercent"])

        st.divider()

        # Confidence distribution
        st.subheader("Confidence Distribution by Category")
        conf_df = summary_df[summary_df["Count"] > 0].copy()
        st.bar_chart(conf_df.set_index("Category")["AvgConfidence"])

    with tab3:
        st.header("Test Browser")

        if detailed_data is None:
            st.warning(
                f"Detailed test data not found: {data_dir / 'unit_test_classification_detailed.jsonl'}"
            )
            return

        st.markdown(f"**Total tests:** {len(detailed_data)}")

        # Filters
        col1, col2, col3 = st.columns(3)

        with col1:
            categories = sorted(set(t["primary_category_name"] for t in detailed_data))
            selected_category = st.selectbox(
                "Filter by primary category:",
                ["All"] + categories,
                key="category_filter",
            )

        with col2:
            methods = ["All", "static", "llm"]
            selected_method = st.selectbox(
                "Filter by method:", methods, key="method_filter"
            )

        with col3:
            min_confidence = st.slider(
                "Min confidence:", 0.0, 1.0, 0.0, 0.1, key="confidence_filter"
            )

        # Apply filters
        filtered = detailed_data
        if selected_category != "All":
            filtered = [
                t for t in filtered if t["primary_category_name"] == selected_category
            ]
        if selected_method != "All":
            filtered = [t for t in filtered if t["method"] == selected_method]
        filtered = [t for t in filtered if t["primary_confidence"] >= min_confidence]

        st.markdown(f"**Filtered tests:** {len(filtered)}")

        # Paginated test viewer
        if filtered:
            tests_per_page = 10
            num_pages = (len(filtered) + tests_per_page - 1) // tests_per_page

            page = st.number_input(
                f"Page (1-{num_pages}):",
                min_value=1,
                max_value=num_pages,
                value=1,
                step=1,
            )

            start_idx = (page - 1) * tests_per_page
            end_idx = min(start_idx + tests_per_page, len(filtered))
            page_tests = filtered[start_idx:end_idx]

            for i, test in enumerate(page_tests, start=start_idx + 1):
                # Build title with primary category and tags
                title_parts = [test["primary_category_name"].split(".")[0]]
                if test.get("tags"):
                    title_parts.append(f"+ {len(test['tags'])} tags")
                title_suffix = " | ".join(title_parts)

                with st.expander(
                    f"Test {i}: {test['test_name']} "
                    f"[{title_suffix}] "
                    f"({test['primary_confidence']:.2f} confidence, {test['method']})"
                ):
                    col1, col2 = st.columns([1, 3])

                    with col1:
                        st.markdown("**Metadata:**")
                        st.markdown(f"- **Sample ID:** {test['pbt_id']}")
                        st.markdown(
                            f"- **Primary Category:** {test['primary_category_name']}"
                        )
                        st.markdown(f"- **Method:** {test['method']}")
                        st.markdown(
                            f"- **Confidence:** {test['primary_confidence']:.2f}"
                        )

                        # Show tags if present
                        if test.get("tags"):
                            st.markdown("**Tags:**")
                            for tag_name in test.get("tag_names", []):
                                st.markdown(f"- {tag_name}")

                        if test.get("signals"):
                            st.markdown("**Signals:**")
                            for signal in test["signals"]:
                                st.markdown(f"- {signal}")

                        if test.get("reasoning"):
                            st.markdown("**LLM Reasoning:**")
                            st.info(test["reasoning"])

                    with col2:
                        st.markdown("**Test Code:**")
                        st.code(test["test_code"], language="python", line_numbers=True)
        else:
            st.info("No tests match the current filters")

    with tab4:
        st.header("Raw Data")

        st.subheader("Summary CSV")
        st.dataframe(summary_df, width="stretch")

        if st.button("📋 Copy CSV Path"):
            st.code(str(data_dir / "unit_test_classification.csv"), language=None)

        st.divider()

        if detailed_data:
            st.subheader("Detailed JSONL")
            st.markdown(f"**Records:** {len(detailed_data)}")

            # Show first few records as JSON
            num_preview = st.slider("Preview records:", 1, 10, 3)
            st.json(detailed_data[:num_preview])

            if st.button("📋 Copy JSONL Path"):
                st.code(
                    str(data_dir / "unit_test_classification_detailed.jsonl"),
                    language=None,
                )


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

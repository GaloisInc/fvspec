"""Streamlit dashboard for exploring accumulated W&B runs.

Launch with (from benchmark/ directory):
    uv run streamlit run src/scripts/postproduction/accumulate/dashboard.py
"""

import json
import tomllib
from pathlib import Path

import pandas as pd
import streamlit as st

# Page config
st.set_page_config(
    page_title="fvspec Post-Production Analysis",
    page_icon="📊",
    layout="wide",
)

st.title("📊 fvspec Post-Production Analysis")
st.markdown("Explore accumulated W&B runs from manifest.toml")


# Load manifest
@st.cache_data
def load_manifest(manifest_path: str) -> dict:
    """Load manifest.toml."""
    with open(manifest_path, "rb") as f:
        return tomllib.load(f)


@st.cache_data
def load_run_metadata(run_dir: Path) -> dict | None:
    """Load metadata.json for a run."""
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.exists():
        return None
    with open(metadata_path) as f:
        return json.load(f)


@st.cache_data
def load_run_history(run_dir: Path) -> pd.DataFrame | None:
    """Load history.csv for a run."""
    history_path = run_dir / "history.csv"
    if not history_path.exists():
        return None
    return pd.read_csv(history_path)


# Sidebar: Manifest and run selection
st.sidebar.header("Configuration")

manifest_path = st.sidebar.text_input(
    "Manifest path",
    value="src/scripts/postproduction/accumulate/manifest.toml",
    help="Path to manifest.toml (relative to benchmark/)",
)

try:
    manifest = load_manifest(manifest_path)
    # Output directory is relative to benchmark/ root
    output_dir = Path(manifest["project"]["output_dir"])

    st.sidebar.success(f"Loaded {len(manifest['run_names'])} runs from manifest")

    # Run selection
    run_options = {run_id: run_id for run_id in manifest["run_names"]}

    if not run_options:
        st.warning("No runs found in manifest.toml")
        st.stop()

    selected_run_label = st.sidebar.selectbox("Select run", list(run_options.keys()))
    selected_run_id = run_options[selected_run_label]

    # Load run data
    run_dir = output_dir / selected_run_id
    if not run_dir.exists():
        st.error(
            f"Run directory not found: {run_dir}\n\n"
            "Run `uv run python -m scripts.postproduction.accumulate sync` to download runs."
        )
        st.stop()

    metadata = load_run_metadata(run_dir)
    history = load_run_history(run_dir)

except FileNotFoundError:
    st.error(f"Manifest not found: {manifest_path}")
    st.stop()
except Exception as e:
    st.error(f"Error loading manifest: {e}")
    st.stop()

# Main content
st.header(f"Run: {metadata['name']}")

# Metadata overview
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("State", metadata["state"])
with col2:
    st.metric("Run ID", metadata["id"])
with col3:
    variant = metadata["config"].get("variant", "unknown")
    st.metric("Variant", variant)
with col4:
    sample_size = metadata["config"].get("sample_size", 0)
    st.metric("Samples", sample_size)

# Tabs for different views
tab1, tab2, tab3, tab4 = st.tabs(["📈 Metrics", "⚙️ Config", "📄 Files", "📋 Summary"])

with tab1:
    st.subheader("Metrics History")

    if history is not None and not history.empty:
        # Show available metrics
        metric_cols = [c for c in history.columns if c != "_step"]

        st.markdown(f"**Available metrics:** {len(metric_cols)}")

        # Metric selection
        selected_metrics = st.multiselect(
            "Select metrics to plot",
            metric_cols,
            default=metric_cols[:3] if len(metric_cols) >= 3 else metric_cols,
        )

        if selected_metrics:
            # Plot selected metrics
            for metric in selected_metrics:
                st.subheader(metric)
                chart_data = history[["_step", metric]].dropna()
                if not chart_data.empty:
                    st.line_chart(chart_data.set_index("_step"))
                else:
                    st.info(f"No data for {metric}")

            # Show raw data
            if st.checkbox("Show raw history data"):
                st.dataframe(history)
        else:
            st.info("Select metrics to visualize")
    else:
        st.warning("No history data available for this run")

with tab2:
    st.subheader("Run Configuration")

    config = metadata["config"]
    st.json(config)

    # Highlight key config values
    st.markdown("### Key Parameters")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Model", config.get("model", "N/A"))
    with col2:
        st.metric("Sample Size", config.get("sample_size", "N/A"))
    with col3:
        ranseed = config.get("ranseed", "N/A")
        st.metric("Random Seed", ranseed)

    # Sequential sampling parameters
    if "start_idx" in config or "end_idx" in config:
        st.markdown("### Sequential Sampling")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Start Index", config.get("start_idx", "N/A"))
        with col2:
            st.metric("End Index", config.get("end_idx", "N/A"))

with tab3:
    st.subheader("Downloaded Files")

    files_dir = run_dir / "files"
    if files_dir.exists():
        # Get all files recursively
        all_files = list(files_dir.rglob("*"))
        files = [f for f in all_files if f.is_file()]

        st.metric("Total Files", len(files))

        # Group by extension
        extensions = {}
        for f in files:
            ext = f.suffix or "no extension"
            extensions[ext] = extensions.get(ext, 0) + 1

        st.markdown("### Files by Extension")
        ext_df = pd.DataFrame(
            [
                {"Extension": k, "Count": v}
                for k, v in sorted(extensions.items(), key=lambda x: -x[1])
            ]
        )
        st.dataframe(ext_df, use_container_width=True)

        # File browser
        st.markdown("### File Browser")
        if files:
            # Group files by directory (sample)
            samples = {}
            for f in files:
                # Get relative path from files_dir
                rel_path = f.relative_to(files_dir)
                parts = rel_path.parts
                if len(parts) > 1:
                    sample_name = parts[0]
                    if sample_name not in samples:
                        samples[sample_name] = []
                    samples[sample_name].append(str(rel_path))

            if samples:
                selected_sample = st.selectbox(
                    "Select sample to view files", sorted(samples.keys())
                )

                st.markdown(f"**Files in {selected_sample}:**")
                for file_path in sorted(samples[selected_sample]):
                    full_path = files_dir / file_path
                    st.code(f"{file_path} ({full_path.stat().st_size} bytes)")

                # File viewer
                selected_file = st.selectbox(
                    "View file content", sorted(samples[selected_sample])
                )

                if selected_file:
                    full_path = files_dir / selected_file
                    try:
                        content = full_path.read_text()
                        if selected_file.endswith(".json"):
                            st.json(json.loads(content))
                        else:
                            st.code(
                                content,
                                language=(
                                    "lean" if selected_file.endswith(".lean") else None
                                ),
                            )
                    except Exception as e:
                        st.error(f"Error reading file: {e}")
            else:
                st.info("No sample directories found")
        else:
            st.info("No files found")
    else:
        st.warning("Files directory not found")

with tab4:
    st.subheader("Run Summary")

    summary = metadata["summary"]
    st.json(summary)

    # Highlight key summary metrics
    if summary:
        st.markdown("### Key Metrics")

        # Success rate
        if "summary/success_rate" in summary:
            st.metric("Success Rate", f"{summary['summary/success_rate']:.1%}")

        # Create metrics grid
        cols = st.columns(3)
        col_idx = 0

        for key, value in sorted(summary.items()):
            if key.startswith("summary/"):
                metric_name = key.replace("summary/", "").replace("_", " ").title()
                if isinstance(value, (int, float)):
                    with cols[col_idx % 3]:
                        st.metric(metric_name, f"{value:.2f}")
                    col_idx += 1

# Sidebar: Additional info
st.sidebar.markdown("---")
st.sidebar.markdown("### Run Info")
st.sidebar.markdown(f"**Created:** {metadata.get('created_at', 'N/A')}")
st.sidebar.markdown(f"**State:** {metadata['state']}")
if metadata.get("tags"):
    st.sidebar.markdown(f"**Tags:** {', '.join(metadata['tags'])}")
if metadata.get("group"):
    st.sidebar.markdown(f"**Group:** {metadata['group']}")

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Local path:** `{run_dir}`")

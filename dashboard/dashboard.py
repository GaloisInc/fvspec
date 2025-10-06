import argparse
from bokeh.models import HoverTool
import hvplot.pandas
import holoviews
import json
import os
from pathlib import Path
from pandas import DataFrame
import panel


def parse_arguments() -> argparse.Namespace:
    """Parses arguments passed in.

    Returns:
        argparse.Namespace: parser
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-d",
        "--directory",
        type=str,
        help="Directory of artifacts.",
        default="../benchmark/artifacts/2025-10-01T13-26-28",
        required=False,
    )
    parser.add_argument(
        "-x",
        "--x_axis",
        type=str,
        help="Dictionary key for x axis.",
        default="interest",
        required=False,
    )
    parser.add_argument(
        "-y",
        "--y_axis",
        type=str,
        help="Dictionary key for y axis.",
        default="faithfulness",
        required=False,
    )
    return parser.parse_args()

panel.extension()
panel.extension("tabulator") 
panel.extension("floatpanel")

def dashboard():
    """
    Example:
        panel serve dashboard.py --args -d "../benchmark/artifacts/2025-10-01T13-26-28" -x "interest" -y "faithfulness" 
    """
    ACCENT = "blue"
    styles = {
        "box-shadow": "rgba(50, 50, 93, 0.25) 0px 6px 12px -2px, rgba(0, 0, 0, 0.3) 0px 3px 7px -3px",
        "border-radius": "4px",
        "padding": "10px",
    }

    args = parse_arguments()

    # Read the contents of the QA files
    data: list[dict] = []
    for dir in os.listdir(args.directory):
        path = Path (args.directory) / dir / "QA.json"
        with open(path, "r") as file:
            data.append(json.load(file))
    dataframe = DataFrame.from_dict(data)

    #count points at each x,y and add as new row
    f_i_row_counts: list[int] = []
    default_row_counts: list[int] = []
    for _, row in dataframe.iterrows():
        f_i_count_val: int = 1
        if dataframe.isin([row["faithfulness"],row["interest"]]).any().any():
            filt_x_df = dataframe[dataframe["faithfulness"] == row["faithfulness"]]
            filt_xy_df = filt_x_df[filt_x_df["interest"] == row["interest"]]
            f_i_count_val = len(filt_xy_df)
        f_i_row_counts.append(f_i_count_val)
        default_row_counts.append(1)
    dataframe["faithfulness vs interest"] = f_i_row_counts
    dataframe["default"] = default_row_counts

    # Make interactive
    interactive_data = dataframe.interactive()
    x_axis_options = list(dataframe.columns)
    y_axis_options = list(dataframe.columns)
    size_options = list(dataframe.columns)
    color_options = list(dataframe.columns)
    x_axis_selector = panel.widgets.Select(name='Select X-Axis', options=x_axis_options, value=args.x_axis, visible=False)
    y_axis_selector = panel.widgets.Select(name='Select Y-Axis', options=y_axis_options, value=args.y_axis, visible=False)
    size_selector = panel.widgets.Select(name='Select Size Weight', options=size_options, value="default", visible=False)
    color_selector = panel.widgets.Select(name='Select Color', options=color_options, value=args.y_axis, visible=False)


    # tooltip with just list of ids & names
    hover = HoverTool(tooltips=[("Sample", "@sample_id @sample_name")], )
    # main plot
    plot = interactive_data.hvplot.scatter(
        title=args.directory,
        x=x_axis_selector,
        y=y_axis_selector,
        c=color_selector,
        size=size_selector,
        scale= 5, #multiply point size by this
        alpha=0.7,
        hover_cols=["sample_name","sample_id"],
        tools=[hover],
        responsive = True,
    )

    visibilities = panel.Column(
        "X:", x_axis_selector.controls(['visible'])[1],"","", 
        "Y:", y_axis_selector.controls(['visible'])[1],"","",
        "Size:", size_selector.controls(['visible'])[1],"","",
        "Color:", color_selector.controls(['visible'])[1],
    )

    plotCol = panel.Column(
        plot,
        sizing_mode="stretch_both",
        name="Plot"
    )
    table = panel.widgets.Tabulator(dataframe, sizing_mode="stretch_both", name="Table")
    tabs = panel.Tabs(
        plotCol, table, styles=styles, sizing_mode="stretch_width", height=600, margin=10
    )

    # some top overview stuff
    indicators = panel.FlexBox(
        panel.indicators.Number(
            value=len(dataframe),
            name="Number DataPoints",
            format="{value:,.0f}",
            styles=styles,
        ),
        panel.indicators.Number(
            value=len(dataframe[dataframe["success"] == True]),
            name="Number Successes",
            format="{value:,.0f}",
            styles=styles,
        ),
    )

    # main layout
    return panel.template.FastListTemplate(
        title="FVSpec Dashboard",
        sidebar=[panel.Column(visibilities, width=80)],
        sidebar_width=60,
        main=[panel.Column(indicators, tabs, sizing_mode="stretch_both")],
        main_layout=None,
        accent=ACCENT,
    )

dashboard().servable()
    
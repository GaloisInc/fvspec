"""Analyze import dependencies in scraped property-based test data.

This script processes the scraped Hypothesis property-based tests from
scrapedtests.json and extracts all Python import statements from both the
test code (pbt) and its dependencies (deps). It then generates a CSV report
counting how many datapoints use each import, sorted by frequency.

The output (import_counts.csv) helps understand:
- Which libraries/modules are most commonly used in the scraped tests
- What dependencies would be needed to run/translate these tests
- The breadth of the Python ecosystem covered by the dataset

Usage:
    uv run analyze_deps

Output:
    ../data/import_counts.csv - CSV file with columns:
        - import: The fully qualified import name
        - number of datapoints using the import: Frequency count
"""

import asyncio
import json
import logging
import re
from pathlib import Path

from pydantic import BaseModel


class Datapoint(BaseModel):
    """Extended datapoint model for analyze_deps script.

    Includes additional fields beyond the core Datapoint model:
    - mode: Processing mode used during scraping
    - summaryversion: Version of the summarization algorithm
    - summaryconfidence: Confidence score for the summary
    """

    id: int
    repo_id: int
    pbt_name: str
    pbt: str
    dep_names: list[str]
    deps: list[str]
    source: str
    summary: str | None
    hash: str
    summary_vector: str | None
    mode: str
    summaryversion: int | None
    summaryconfidence: int | None


UP = Path("..")


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    # Read the content of the file

    with open(UP / "data" / "scrapedtests.json", "r") as file:
        data = json.load(file)

    # Find all the imports in each datapoint
    imports_per_datapoint: list[str] = []
    for datapoint in [Datapoint(**obj) for obj in data]:  # type: ignore[arg-type]
        import_strs: list[str] = []
        import_strs += process(datapoint.pbt)
        for dep in datapoint.deps:
            import_strs += process(dep)
        import_strs = list(set(import_strs))  # remove duplicates
        imports_per_datapoint += import_strs

    # Count up each import
    import_list: list[tuple[str, int]] = []
    processed_str: list[str] = []
    for imp in imports_per_datapoint:
        if processed_str.count(imp) == 0:
            processed_str.append(imp)
            import_list.append((imp, imports_per_datapoint.count(imp)))

    # Output results
    import_list.sort(key=lambda x: x[1])
    with open(UP / "data" / "import_counts.csv", "w") as file:
        file.write("import,number of datapoints using the import\n")
        for imp, n in import_list:
            file.write(imp + ", " + str(n) + "\n")


FROM_IMPORT_RE = (
    r"(\bfrom[\s]+[\S]+)?[\s]+import[\s]+([A-Za-z0-9_\.]+)(\s*,\s*[A-Za-z0-9_\.]+)*"
)
IN_LINE_COMMENTS_RE = r"#.*"
MULTI_LINE_COMMENTS_RE = r"\"\"\"[\s\S]*\"\"\""


def process(code: str) -> list[str]:
    """Extract import statements from Python source code.

    Parses Python code to find all import and from...import statements,
    resolving fully qualified import names. Handles both simple and
    complex import patterns including comma-separated imports.

    Args:
        code: Python source code string

    Returns:
        List of fully qualified import names (e.g., ['numpy.array', 'hypothesis.strategies'])
    """
    # remove comments
    code = re.sub(IN_LINE_COMMENTS_RE, "", code)
    code = re.sub(MULTI_LINE_COMMENTS_RE, "", code)

    imports = []
    matches = re.findall(FROM_IMPORT_RE, code)
    for match in matches:
        # find any [from <import_from>] import <a>[, <b>]*
        if match[0].startswith("from"):
            for i in (1, len(match) - 1):
                # remove "from " and any leading "."s
                import_from = match[0].replace("from", "")
                import_from = import_from.lstrip()
                if import_from.startswith("."):
                    import_from = import_from[1:]
                if import_from.startswith("."):
                    import_from = import_from[1:]
                # remove any leading ", "s and preapend <import_from>
                import_class = match[i].replace(",", "")
                import_class = import_class.lstrip()
                if import_class != "" and import_from != "":
                    imports.append(import_from + "." + import_class)
                elif import_class != "":
                    imports.append(import_class)
        else:
            for m in match:
                import_class = m.replace(",", "")
                import_class = import_class.lstrip()
                if import_class != "":
                    imports.append(import_class)

    return imports


def cli():
    """Entry point for the analyze_deps command."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()

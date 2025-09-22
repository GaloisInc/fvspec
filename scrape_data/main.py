import asyncio
import json
import logging
import re


class Datapoint:
    def __init__(
        self,
        id: int,
        repo_id: int,
        pbt_name: str,
        pbt: str,
        dep_names: list[str],
        deps: list[str],
        source: str,
        summary: str | None,
        hash: str,
        summary_vector: str | None,
        mode: str,
        summaryversion: int,
        summaryconfidence: int,
    ):
        self.id = id
        self.repo_id = repo_id
        self.pbt_name = pbt_name
        self.pbt = pbt
        self.dep_names = dep_names
        self.deps = deps
        self.source = source
        self.summary = summary
        self.hash = hash
        self.summary_vector = summary_vector
        self.mode = mode
        self.summaryversion = summaryversion
        self.summaryconfidence = summaryconfidence


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    # Read the content of the file
    with open("../data/scrapedtests.json", "r") as file:
        data = json.load(file)

    # Find all the imports in each datapoint
    imports_per_datapoint: list[str] = []
    for datapoint in [Datapoint(**obj) for obj in data]:
        import_strs: list[str] = []
        import_strs += process(datapoint.pbt)
        for dep in datapoint.deps:
            import_strs += process(dep)
        import_strs = list(set(import_strs))  # remove duplicates
        imports_per_datapoint += import_strs

    # Count up each import
    import_list: list[(str, int)] = []
    processed_str: list[str] = []
    for imp in imports_per_datapoint:
        if processed_str.count(imp) == 0:
            processed_str.append(imp)
            import_list.append((imp, imports_per_datapoint.count(imp)))

    # Output results
    import_list.sort(key=lambda x: x[1])
    with open("../data/import_counts.csv", "w") as file:
        file.write("import,number of datapoints using the import\n")
        for imp, n in import_list:
            file.write(imp + ", " + str(n) + "\n")


FROM_IMPORT_RE = (
    r"(\bfrom[\s]+[\S]+)?[\s]+import[\s]+([A-Za-z0-9_\.]+)(\s*,\s*[A-Za-z0-9_\.]+)*"
)
IN_LINE_COMMENTS_RE = r"#.*"
MULTI_LINE_COMMENTS_RE = r"\"\"\"[\s\S]*\"\"\""


def process(code: str) -> list[str]:
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


if __name__ == "__main__":
    asyncio.run(main())

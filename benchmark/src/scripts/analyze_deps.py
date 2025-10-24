"""Rich dependency analysis for property-based tests.

This script reads the scraped Hypothesis dataset and produces a dependency
report tailored for the dependency-mocking subgroup. Whereas the legacy
``analyze_deps_regex`` utility simply counted import strings, this tool
introspects parsed Python ASTs, tracks actual call sites, and surfaces
contextual examples so the team can scope mocking effort intelligently.

Outputs (written to ``benchmark/data`` by default):

- ``dependency_report.json`` with detailed structured metrics
- ``dependency_report.md`` as a human-readable brief

Usage:
    uv run analyze-deps [--limit-modules 30] [--limit-symbols 40]
                        [--sample-size 100] [--seed 0]
"""

from __future__ import annotations

import ast
import json
import jsonlines
import logging
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal, Sequence

import random

import typer
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models import RequestUsage
from pydantic_ai.models.function import FunctionModel

# --------------------------------------------------------------------------- #
# Path constants
# --------------------------------------------------------------------------- #


SCRIPT_PATH = Path(__file__).resolve()
BENCHMARK_DIR = SCRIPT_PATH.parents[2]
DATA_DIR = BENCHMARK_DIR / "data"
DEFAULT_DATASET_PATH = DATA_DIR / "pbts.jsonl"
DEFAULT_OUTPUT_DIR = DATA_DIR

# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #


class Datapoint(BaseModel):
    """Dataset record describing a property-based test and its dependencies."""

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
    mode: str | None = None
    summaryversion: int | None = None
    summaryconfidence: int | None = None
    has_overlap_data: bool | None = None
    repo_name: str | None = None
    repo_url: str | None = None
    analysis_timestamp: str | None = None
    pbt_summary: str | None = None
    pbt_functions: list[str] | None = None
    overlapping_tests: list[dict[str, Any]] | None = None


class CallExample(BaseModel):
    """A representative call site for a dependency."""

    datapoint_id: int
    module_root: str
    symbol: str
    code_line: str = Field(..., description="Trimmed source line containing the call")
    source: str
    snippet_kind: Literal["pbt", "dep"]


class ModuleUsage(BaseModel):
    """Aggregated usage information for a module root."""

    module: str
    datapoint_count: int
    category: Literal["stdlib", "third_party", "local", "unknown"]
    distinct_imports: list[str]
    representative_symbols: list[str]
    examples: list[CallExample]


class SymbolUsage(BaseModel):
    """Usage information for a fully-qualified symbol."""

    symbol: str
    datapoint_count: int
    module: str


class MockTarget(ModuleUsage):
    """Modules recommended for mocking attention."""

    notes: str


class InlineDepSummary(BaseModel):
    """Statistics about inlined dependency payloads."""

    datapoints_with_deps: int
    avg_deps_per_datapoint: float
    top_dep_names: list[tuple[str, int]]


class NonPythonSample(BaseModel):
    """Examples of datapoints that do not parse cleanly as Python."""

    datapoint_id: int
    source: str
    glimpse: str
    reason: str


class DatasetOverview(BaseModel):
    """High-level dataset metrics."""

    total_datapoints: int
    python_datapoints: int
    non_python_datapoints: int
    datapoints_with_inline_deps: int


class DependencyReport(BaseModel):
    """Top-level report structure persisted to disk."""

    analysis: "AnalysisConfig"
    overview: DatasetOverview
    top_modules: list[ModuleUsage]
    top_symbols: list[SymbolUsage]
    mock_priorities: list[MockTarget]
    io_hotspots: list[ModuleUsage]
    inline_dependency_summary: InlineDepSummary
    non_python_samples: list[NonPythonSample]


class AnalysisConfig(BaseModel):
    """Configuration used for the current dependency analysis run."""

    dataset: str
    output_dir: str
    limit_modules: int
    limit_symbols: int
    sample_size: int | None = None
    seed: int
    ranseed: int
    verbose: bool


# --------------------------------------------------------------------------- #
# AST helpers
# --------------------------------------------------------------------------- #


@dataclass
class CallRecord:
    """Internal representation of a resolved call."""

    symbol: str
    module_root: str
    lineno: int
    code_line: str


class ImportRegistry:
    """Track aliases introduced by import statements."""

    def __init__(self) -> None:
        """Initialise an empty alias mapping."""
        self._alias_to_target: dict[str, str] = {}

    def add_import(self, alias_name: str, target: str) -> None:
        """Register ``alias_name`` as pointing to ``target``."""
        if alias_name:
            self._alias_to_target.setdefault(alias_name, target)

    def resolve_name(self, name: str) -> str:
        """Resolve a possibly-aliased symbol name to its target."""
        return self._alias_to_target.get(name, name)

    def resolve_dotted(self, dotted: str) -> str:
        """Resolve dotted names while respecting stored aliases."""
        if "." not in dotted:
            return self.resolve_name(dotted)
        first, *rest = dotted.split(".")
        resolved_first = self.resolve_name(first)
        if rest:
            if resolved_first == first:
                return dotted
            return ".".join([resolved_first, *rest])
        return resolved_first


class CodeAnalyzer(ast.NodeVisitor):
    """Traverse Python ASTs to gather imports and call sites."""

    def __init__(self, code: str, snippet_kind: Literal["pbt", "dep"]) -> None:
        """Prepare analysis state for a snippet of the provided ``snippet_kind``."""
        self.code_lines = code.splitlines()
        self.snippet_kind = snippet_kind
        self.registry = ImportRegistry()
        self.modules: set[str] = set()
        self.symbols: set[str] = set()
        self.call_records: list[CallRecord] = []
        self.attributes: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        """Track modules introduced via ``import`` statements."""
        for alias in node.names:
            module = alias.name
            alias_name = alias.asname or module.split(".")[0]
            self.registry.add_import(alias_name, module)
            self.modules.add(module)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Track modules introduced via ``from ... import`` statements."""
        module = node.module or ""
        if node.level:
            module = "." * node.level + module
        module = module.strip(".")
        for alias in node.names:
            if alias.name == "*":
                self.modules.add(module or "*")
                continue
            target = f"{module}.{alias.name}" if module else alias.name
            alias_name = alias.asname or alias.name
            self.registry.add_import(alias_name, target)
            self.modules.add(target)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Record function or method invocations encountered in the AST."""
        symbol = self._resolve_callable(node.func)
        if symbol:
            resolved = self.registry.resolve_dotted(symbol)
            module_root = resolved.split(".")[0]
            code_line = self._safe_line(node.lineno - 1)
            self.symbols.add(resolved)
            self.call_records.append(
                CallRecord(
                    symbol=resolved,
                    module_root=module_root,
                    lineno=node.lineno,
                    code_line=code_line,
                )
            )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Collect attribute-access chains for potential module references."""
        chain = self._attribute_chain(node)
        if chain:
            resolved = self.registry.resolve_dotted(chain)
            self.attributes.add(resolved)
        self.generic_visit(node)

    def _attribute_chain(self, node: ast.AST) -> str | None:
        parts: list[str] = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
            return ".".join(reversed(parts))
        return None

    def _resolve_callable(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return self._attribute_chain(node)
        return None

    def _safe_line(self, index: int) -> str:
        if index < 0 or index >= len(self.code_lines):
            return ""
        line = self.code_lines[index].strip()
        if len(line) > 160:
            return line[:157] + "..."
        return line


# --------------------------------------------------------------------------- #
# Dataset streaming
# --------------------------------------------------------------------------- #


def stream_jsonl(path: Path) -> Iterator[dict]:
    """Stream JSONL file line by line to avoid loading the entire dataset into RAM."""
    with jsonlines.open(path) as reader:
        yield from reader


def reservoir_sample_jsonl(
    iterator: Iterator[dict], sample_size: int, seed: int
) -> list[dict]:
    """Reservoir sample a fixed number of objects from an iterator."""
    rng = random.Random(seed)
    sample: list[dict] = []
    for idx, obj in enumerate(iterator):
        if idx < sample_size:
            sample.append(obj)
        else:
            j = rng.randint(0, idx)
            if j < sample_size:
                sample[j] = obj
    return sample


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #


STD_MODULES = set(sys.stdlib_module_names)
IO_ROOTS = {"os", "pathlib", "tempfile", "shutil", "subprocess", "io", "gzip", "bz2"}
NETWORK_ROOTS = {"requests", "urllib", "httpx", "http", "aiohttp"}


class DependencyAggregator:
    """Collect dataset-wide dependency signals."""

    def __init__(self, example_limit: int = 3) -> None:
        """Initialise aggregation counters and storage structures."""
        self.total_datapoints = 0
        self.python_datapoints = 0
        self.datapoints_with_inline_deps = 0

        self.module_datapoints: dict[str, set[int]] = defaultdict(set)
        self.module_full_names: dict[str, set[str]] = defaultdict(set)
        self.module_symbol_counts: dict[str, Counter[str]] = defaultdict(Counter)
        self.module_examples: dict[str, list[CallExample]] = defaultdict(list)

        self.symbol_datapoints: dict[str, set[int]] = defaultdict(set)

        self.dep_name_counter: Counter[str] = Counter()
        self.dep_total_entries = 0

        self.non_python_samples: dict[int, NonPythonSample] = {}
        self.example_limit = example_limit

    def consume(self, datapoint: Datapoint) -> None:
        """Record dependency statistics for a single datapoint."""
        self.total_datapoints += 1
        if datapoint.dep_names:
            self.datapoints_with_inline_deps += 1
            self.dep_name_counter.update(datapoint.dep_names)
            self.dep_total_entries += len(datapoint.dep_names)

        pbt_result = self._analyze_snippet(datapoint, datapoint.pbt, "pbt")
        if pbt_result:
            self.python_datapoints += 1
        else:
            self._note_non_python(
                datapoint.id, datapoint.source, datapoint.pbt, "pbt failed to parse"
            )

        for dep_text in datapoint.deps:
            dep_result = self._analyze_snippet(datapoint, dep_text, "dep")
            if dep_result is None:
                self._note_non_python(
                    datapoint.id, datapoint.source, dep_text, "dep failed to parse"
                )

    def _analyze_snippet(
        self,
        datapoint: Datapoint,
        source_text: str,
        snippet_kind: Literal["pbt", "dep"],
    ) -> CodeAnalyzer | None:
        stripped = source_text.strip()
        if not stripped:
            return None
        try:
            tree = ast.parse(source_text)
        except SyntaxError:
            return None
        analyzer = CodeAnalyzer(source_text, snippet_kind)
        analyzer.visit(tree)
        self._register_modules(datapoint.id, analyzer.modules)
        self._register_symbols(datapoint.id, analyzer.symbols)
        self._register_calls(datapoint, analyzer.call_records, snippet_kind)
        return analyzer

    def _register_modules(self, datapoint_id: int, modules: Iterable[str]) -> None:
        for module in modules:
            if not module:
                continue
            root = module.split(".")[0]
            self.module_datapoints[root].add(datapoint_id)
            self.module_full_names[root].add(module)

    def _register_symbols(self, datapoint_id: int, symbols: Iterable[str]) -> None:
        for symbol in symbols:
            if not symbol:
                continue
            self.symbol_datapoints[symbol].add(datapoint_id)
            root = symbol.split(".")[0]
            self.module_datapoints[root].add(datapoint_id)
            self.module_symbol_counts[root][symbol] += 1

    def _register_calls(
        self,
        datapoint: Datapoint,
        call_records: Sequence[CallRecord],
        snippet_kind: Literal["pbt", "dep"],
    ) -> None:
        for record in call_records:
            root = record.module_root
            if len(self.module_examples[root]) >= self.example_limit:
                continue
            example = CallExample(
                datapoint_id=datapoint.id,
                module_root=root,
                symbol=record.symbol,
                code_line=record.code_line,
                source=datapoint.source,
                snippet_kind=snippet_kind,
            )
            self.module_examples[root].append(example)

    def _note_non_python(
        self, datapoint_id: int, source: str, raw_text: str, reason: str
    ) -> None:
        if datapoint_id in self.non_python_samples:
            return
        glimpse = raw_text.strip().splitlines()
        preview = glimpse[0].strip() if glimpse else ""
        if len(preview) > 160:
            preview = preview[:157] + "..."
        self.non_python_samples[datapoint_id] = NonPythonSample(
            datapoint_id=datapoint_id,
            source=source,
            glimpse=preview,
            reason=reason,
        )

    def build_report(
        self,
        module_limit: int,
        symbol_limit: int,
        analysis_config: AnalysisConfig,
    ) -> DependencyReport:
        """Assemble a summarized dependency report from accumulated statistics."""
        top_modules = self._build_top_modules(module_limit)
        top_symbols = self._build_top_symbols(symbol_limit)
        mock_priorities = self._build_mock_targets(top_modules)
        io_hotspots = [
            module
            for module in top_modules
            if module.module in IO_ROOTS or module.module in NETWORK_ROOTS
        ]

        overview = DatasetOverview(
            total_datapoints=self.total_datapoints,
            python_datapoints=self.python_datapoints,
            non_python_datapoints=self.total_datapoints - self.python_datapoints,
            datapoints_with_inline_deps=self.datapoints_with_inline_deps,
        )

        inline_summary = self._build_inline_dep_summary()
        non_python_samples = list(self.non_python_samples.values())[:10]

        return DependencyReport(
            analysis=analysis_config,
            overview=overview,
            top_modules=top_modules,
            top_symbols=top_symbols,
            mock_priorities=mock_priorities,
            io_hotspots=io_hotspots,
            inline_dependency_summary=inline_summary,
            non_python_samples=non_python_samples,
        )

    def _build_top_modules(self, limit: int) -> list[ModuleUsage]:
        items = sorted(
            self.module_datapoints.items(),
            key=lambda pair: len(pair[1]),
            reverse=True,
        )
        results: list[ModuleUsage] = []
        for module, datapoints in items[:limit]:
            category = categorize_module(module)
            distinct_imports = sorted(self.module_full_names[module])
            symbol_counter = self.module_symbol_counts[module]
            top_symbols = [sym for sym, _ in symbol_counter.most_common(5)]
            examples = self.module_examples.get(module, [])
            results.append(
                ModuleUsage(
                    module=module,
                    datapoint_count=len(datapoints),
                    category=category,
                    distinct_imports=distinct_imports,
                    representative_symbols=top_symbols,
                    examples=examples,
                )
            )
        return results

    def _build_top_symbols(self, limit: int) -> list[SymbolUsage]:
        items = sorted(
            self.symbol_datapoints.items(),
            key=lambda pair: len(pair[1]),
            reverse=True,
        )
        result: list[SymbolUsage] = []
        for symbol, datapoints in items[:limit]:
            module_root = symbol.split(".")[0]
            result.append(
                SymbolUsage(
                    symbol=symbol,
                    datapoint_count=len(datapoints),
                    module=module_root,
                )
            )
        return result

    def _build_mock_targets(self, modules: list[ModuleUsage]) -> list[MockTarget]:
        targets: list[MockTarget] = []
        for module in modules:
            if module.category != "third_party":
                continue
            notes = derive_mocking_notes(module)
            targets.append(
                MockTarget(
                    module=module.module,
                    datapoint_count=module.datapoint_count,
                    category=module.category,
                    distinct_imports=module.distinct_imports,
                    representative_symbols=module.representative_symbols,
                    examples=module.examples,
                    notes=notes,
                )
            )
        return targets

    def _build_inline_dep_summary(self) -> InlineDepSummary:
        if self.datapoints_with_inline_deps == 0:
            avg = 0.0
        else:
            avg = self.dep_total_entries / self.datapoints_with_inline_deps
        top_dep_names = self.dep_name_counter.most_common(10)
        return InlineDepSummary(
            datapoints_with_deps=self.datapoints_with_inline_deps,
            avg_deps_per_datapoint=round(avg, 2),
            top_dep_names=top_dep_names,
        )


# --------------------------------------------------------------------------- #
# Categorisation utilities
# --------------------------------------------------------------------------- #


LOCAL_PREFIXES = {
    "tests",
    "src",
    "app",
    "project",
    "example",
}

MOCK_NOTE_HINTS = {
    "torch": "Covers tensor ops, quantization (`torch.ops.fbgemm`), and CUDA guards. Provide CPU-safe kernels and gate GPU availability.",
    "numpy": "Array creation, dtype conversion, and vectorize usage show up. Offer dense array mocks with predictable broadcasting.",
    "pandas": "DataFrame construction/assertions pop up; light-weight DataFrame shim or columnar dict compatibility is sufficient.",
    "requests": "HTTP fetch helpers invoked; swap in a deterministic response layer or fixture-based transport.",
    "sklearn": "Model APIs likely heavy; consider stubbing fit/predict with simple linear models.",
    "scipy": "Scientific routines used; decide whether to support or to skip datapoints requiring SciPy.",
    "pytest": "Pytest helpers imported—mostly harmless, but watch for monkeypatch fixtures.",
    "hypothesis": "Core library already required; ensure strategy aliases map cleanly to Lean specifications.",
    "tensorflow": "If present, emulate tensor shapes similarly to PyTorch mocks.",
}


def categorize_module(
    module_root: str,
) -> Literal["stdlib", "third_party", "local", "unknown"]:
    """Classify a module root into stdlib, third-party, local, or unknown."""
    if module_root in STD_MODULES:
        return "stdlib"
    if module_root in LOCAL_PREFIXES or module_root.startswith("_"):
        return "local"
    if "." in module_root:
        base = module_root.split(".")[0]
        if base in STD_MODULES:
            return "stdlib"
        if base in LOCAL_PREFIXES:
            return "local"
    if module_root:
        return "third_party"
    return "unknown"


def derive_mocking_notes(module: ModuleUsage) -> str:
    """Provide human-readable mocking guidance for a module usage."""
    hint = MOCK_NOTE_HINTS.get(module.module)
    if hint:
        return hint
    top_symbols = ", ".join(module.representative_symbols[:3]) or "import usage"
    return f"Third-party usage anchored on {top_symbols}; review examples for scope."


# --------------------------------------------------------------------------- #
# Reporting helpers
# --------------------------------------------------------------------------- #


def build_summary_text(report: DependencyReport) -> str:
    """Render a short narrative summary."""
    lines: list[str] = []
    overview = report.overview
    lines.append(
        f"Processed {overview.total_datapoints} datapoints; "
        f"{overview.python_datapoints} parsed as Python and "
        f"{overview.datapoints_with_inline_deps} shipped inline dependency stubs."
    )
    if report.mock_priorities:
        lines.append("")
        lines.append("Mocking priorities:")
        for target in report.mock_priorities[:8]:
            lines.append(
                f"- {target.module} ({target.datapoint_count} datapoints): "
                f"{target.notes}"
            )
    if report.io_hotspots:
        lines.append("")
        lines.append(
            "I/O / network hotspots: "
            + ", ".join(f"{m.module} ({m.datapoint_count})" for m in report.io_hotspots)
        )
    if report.non_python_samples:
        sample = report.non_python_samples[0]
        lines.append("")
        lines.append(
            f"First non-Python sample (#{sample.datapoint_id}): {sample.glimpse} :: {sample.reason}"
        )
    if report.inline_dependency_summary.datapoints_with_deps:
        ids = report.inline_dependency_summary.datapoints_with_deps
        avg = report.inline_dependency_summary.avg_deps_per_datapoint
        names = ", ".join(
            f"{name} ({count})"
            for name, count in report.inline_dependency_summary.top_dep_names[:5]
        )
        lines.append("")
        lines.append(
            f"{ids} datapoints ship helper definitions (avg {avg} per datapoint). "
            f"Top inlined names: {names}"
        )
    return "\n".join(lines)


def summarise_with_agent(summary_text: str) -> str:
    """Use a pydantic-ai FunctionModel Agent to surface the narrative summary."""

    def function_model(messages, agent_info):  # type: ignore[override]
        return ModelResponse(
            parts=[TextPart(content=summary_text)],
            usage=RequestUsage(),
        )

    agent = Agent(
        FunctionModel(function=function_model, model_name="function:deps-summary"),
        name="dependency-summary",
        instructions=[
            "You are summarising dependency analysis findings for the dep-mocking pod.",
            "Highlight actionable takeaways without re-flowing the provided summary.",
        ],
        output_type=str,
    )
    result = agent.run_sync("Report dependency insights succinctly.")
    return result.output


def render_markdown(report: DependencyReport, summary: str) -> str:
    """Build a markdown briefing."""
    lines: list[str] = []
    frontmatter_data = report.analysis.model_dump()
    lines.append("---")
    for key, value in frontmatter_data.items():
        lines.append(f"{key}: {json.dumps(value)}")
    lines.append("---")
    lines.append("# Dependency Insights")
    lines.append("")
    lines.append(summary)
    lines.append("")

    lines.append("## Top Modules")
    for module in report.top_modules:
        lines.append(
            f"- **{module.module}** · {module.datapoint_count} datapoints · {module.category}"
        )
        if module.representative_symbols:
            lines.append(f"  - Symbols: {', '.join(module.representative_symbols)}")
        if module.examples:
            example = module.examples[0]
            lines.append(f"  - Example [{example.datapoint_id}] {example.code_line}")

    if report.mock_priorities:
        lines.append("")
        lines.append("## Suggested Mock Targets")
        for target in report.mock_priorities:
            lines.append(
                f"- **{target.module}** ({target.datapoint_count} datapoints): {target.notes}"
            )

    if report.inline_dependency_summary.datapoints_with_deps:
        ids = report.inline_dependency_summary.datapoints_with_deps
        avg = report.inline_dependency_summary.avg_deps_per_datapoint
        lines.append("")
        lines.append("## Inline Dependency Payloads")
        lines.append(f"- Datapoints with inline deps: {ids} (avg {avg} per datapoint)")
        top = report.inline_dependency_summary.top_dep_names[:8]
        if top:
            formatted = ", ".join(f"{name} ({count})" for name, count in top)
            lines.append(f"- Top names: {formatted}")

    if report.non_python_samples:
        lines.append("")
        lines.append("## Non-Python Samples")
        for sample in report.non_python_samples:
            lines.append(
                f"- #{sample.datapoint_id} from {sample.source}: {sample.glimpse} ({sample.reason})"
            )

    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


logger = logging.getLogger("analyze_deps")


def configure_logging(verbose: bool) -> None:
    """Configure module-level logging for the command-line interface."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(message)s")


def iter_datapoints(
    dataset_path: Path, sample_size: int | None, seed: int
) -> Iterator[Datapoint]:
    """Yield datapoints from ``dataset_path``, optionally sampling deterministically."""
    source_iter: Iterable[dict]
    if sample_size is None:
        source_iter = stream_jsonl(dataset_path)
    else:
        source_iter = reservoir_sample_jsonl(
            stream_jsonl(dataset_path), sample_size, seed
        )
    for obj in source_iter:
        try:
            yield Datapoint(**obj)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load datapoint: %s", exc)


def analyze_dataset(
    dataset_path: Path,
    module_limit: int,
    symbol_limit: int,
    sample_size: int | None,
    seed: int,
    analysis_config: AnalysisConfig,
) -> tuple[DependencyReport, str]:
    """Analyze a dataset and return both the structured report and summary text."""
    aggregator = DependencyAggregator()
    for datapoint in iter_datapoints(dataset_path, sample_size, seed):
        aggregator.consume(datapoint)
    if sample_size is not None:
        logger.info(
            "Sampled %s datapoints using seed=%s", aggregator.total_datapoints, seed
        )
    report = aggregator.build_report(module_limit, symbol_limit, analysis_config)
    summary_text = build_summary_text(report)
    if sample_size is not None:
        summary_text += f"\n\nSubset analyzed: random sample of {aggregator.total_datapoints} datapoints (seed={seed})."
    agent_summary = summarise_with_agent(summary_text)
    return report, agent_summary


def write_outputs(report: DependencyReport, summary: str, output_dir: Path) -> None:
    """Persist the dependency report and Markdown summary to ``output_dir``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "dependency_report.json"
    markdown_path = output_dir / "dependency_report.md"
    json_path.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report, summary) + "\n", encoding="utf-8")
    logger.info("Wrote %s and %s", json_path, markdown_path)


def cli(
    dataset: Path = typer.Option(
        DEFAULT_DATASET_PATH,
        "--dataset",
        help="Path to pbts.jsonl",
    ),
    output_dir: Path = typer.Option(
        DEFAULT_OUTPUT_DIR,
        "--output-dir",
        help="Directory for report artifacts",
    ),
    limit_modules: int = typer.Option(
        30, "--limit-modules", help="Number of modules to surface"
    ),
    limit_symbols: int = typer.Option(
        40, "--limit-symbols", help="Number of symbols to surface"
    ),
    sample_size: int | None = typer.Option(
        None,
        "--sample-size",
        help="Reservoir sample this many datapoints before analysis (default: entire dataset).",
    ),
    seed: int = typer.Option(
        0, "--seed", help="Random seed used when sampling datapoints."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """CLI entry point."""
    configure_logging(verbose)
    if not dataset.exists():
        typer.echo(f"Dataset not found at {dataset}", err=True)
        raise typer.Exit(code=1)
    if sample_size is not None and sample_size <= 0:
        typer.echo("--sample-size must be a positive integer", err=True)
        raise typer.Exit(code=1)

    typer.echo("Analyzing dependencies ...")
    analysis_config = AnalysisConfig(
        dataset=str(dataset),
        output_dir=str(output_dir),
        limit_modules=limit_modules,
        limit_symbols=limit_symbols,
        sample_size=sample_size,
        seed=seed,
        ranseed=seed,
        verbose=verbose,
    )
    report, summary = analyze_dataset(
        dataset,
        limit_modules,
        limit_symbols,
        sample_size,
        seed,
        analysis_config,
    )
    write_outputs(report, summary, output_dir)
    typer.echo("")
    typer.echo(summary)


def main() -> None:
    """Execute the ``analyze_deps`` CLI via Typer."""
    typer.run(cli)


if __name__ == "__main__":
    main()

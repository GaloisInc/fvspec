import json
from pathlib import Path
from pydantic import BaseModel
from inspect_ai.dataset import Sample, MemoryDataset
from benchmark.templates.prompt import initial


class Datapoint(BaseModel, frozen=True):
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


class Prompt(BaseModel, frozen=True):
    pbt: str
    deps: list[str]


def datapoint_to_prompt(dp: Datapoint) -> Prompt:
    return Prompt(pbt=dp.pbt, deps=dp.deps)


def mk_initial(prompt: Prompt) -> str:
    return initial.render(pbt=prompt.pbt, deps=prompt.deps)


def load_datapoints(file_path: Path) -> list[Datapoint]:
    """Effectful function: reads a json file from disk"""
    with open(file_path) as f:
        data = json.load(f)
    return [Datapoint(**obj) for obj in data]


def mk_dataset(path: Path) -> MemoryDataset:
    return MemoryDataset(
        [
            Sample(
                input=mk_initial(datapoint_to_prompt(datapoint)),
                metadata={"datapoint": datapoint},
            )
            for datapoint in load_datapoints(path)
        ]
    )

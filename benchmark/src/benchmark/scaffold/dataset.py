import datetime
import json
from pathlib import Path
import random
from pydantic import BaseModel
from inspect_ai.dataset import Sample, MemoryDataset
from benchmark.templates.prompt import initial

random.seed(0)


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

    def toJSON(self):
        return json.dumps(self.__dict__, indent=4)

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


def sample_datapoints(file_path: Path, n: int) -> list[Datapoint]:
    """Effectful function: reads a json file from disk and samples n datapoints at random"""
    dps = load_datapoints(file_path)
    return random.sample(dps, n)


def mk_dataset(path: Path, date_time: datetime) -> MemoryDataset:
    return MemoryDataset(
        [
            Sample(
                input=mk_initial(datapoint_to_prompt(datapoint)),
                metadata={"datapoint": datapoint, "date_time": date_time.strftime("%Y-%m-%dT%H-%M-%S")},
                id=str(datapoint.id)+"_"+datapoint.pbt_name
            )
            for datapoint in sample_datapoints(path, n=100)
        ]
    )

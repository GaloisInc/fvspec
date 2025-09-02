import json
from pathlib import Path
from typer import Typer
from benchmark.templates.prompt import system, initial

DATA = Path("data")

app = Typer()


@app.command()
def preview_prompts(data: str):
    the_json = DATA / data
    with open(the_json) as f:
        data = json.load(f)
    for obj in data:
        print(system.render())
        print(initial.render(pbt=obj["pbt"], deps=obj["deps"]))
        print("=========================")


def main():
    app()

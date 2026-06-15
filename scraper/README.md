# Hypothesis Test Github Scraping

A repository for scraping hypothesis tests and their contexts (all functions in the repo called by the hypothesis test) from Github

# System Requirements

- Python 3.12 (pinned via `.python-version`)
- [uv](https://docs.astral.sh/uv/)
- [Ripgrep](https://github.com/BurntSushi/ripgrep)

# Installation

This is a [uv](https://docs.astral.sh/uv/) project. To install dependencies into a
managed virtual environment, run:

```
uv sync
```

`uv` will provision the pinned Python interpreter and resolve dependencies from
`uv.lock`. There is no longer a `requirements.txt`; `pyproject.toml` and
`uv.lock` are the source of truth.

# Directory Structure

```
.
|-- README.md
|-- data-gh-100.ndjson - Example hypothesis scrape ndjson file
|-- dependents.json - A json file of all github repos stated as "dependents" of the Hypothesis gtihub repo
|-- examples - various example projects with hypothesis tests
|-- parse.py - contains files for parsing codebases with hypothesis tests
|-- pyproject.toml - project metadata and dependencies (uv)
|-- uv.lock - locked dependency versions
|-- main.py (explained in usage)
```

# Usage

The scraper reads from the [dependency graph](https://github.com/HypothesisWorks/hypothesis/network/dependents) of the Hypothesis Github page. The dependents were pre-scraped (by me), and can be found in `dependents.json`. It expects a GitHub token and database connection details in the environment (see `.env` / `python-dotenv`).

Run it via the `scraper` console script:

```
uv run scraper --mode dependents
```

```
usage: scraper [-h] --mode {dependents,gh} [--stale-date STALE_DATE]
               [--timeout TIMEOUT]

Scrape from dependents

options:
  -h, --help            show this help message and exit
  --mode {dependents,gh}
                        Mode to run in (dependents or gh)
  --stale-date STALE_DATE
                        By default, the script skips repos it has already parsed. If you want to reparse, set
                        the stale date (YYYY-MM-DD)
  --timeout TIMEOUT     Timeout for processing a single repository
```

# Extra

To see an example of the parser in action, run `parser.py`, which parses an example repo

## Todo

- [x] License checking
- [x] Write to SQL
- [x] Share code between `scrape-from-gh.py` and `scrape-from-dependents.py`
- [x] Extract function being tested

# Hypothesis Test Github Scraping

A repository for scraping hypothesis tests and their contexts (all functions in the repo called by the hypothesis test) from Github

# System Requirements

- Python 3.12.3 or greater
- [Ripgrep](https://github.com/BurntSushi/ripgrep)

# Python Library Requirements

- astor 0.8.1 or greater
- tqdm 4.64.1 or greater
- PyGithub 1.55 or greater
- pandas 1.4.2 or greater (optional)
- aiohttp

To install, just do `pip install -r requirements.txt`

# Directory Structure

```
.
|-- README.md
|-- data-gh-100.ndjson - Example hypothesis scrape ndjson file
|-- dependents.json - A json file of all github repos stated as "dependents" of the Hypothesis gtihub repo
|-- examples - various example projects with hypothesis tests
|-- parse.py - contains files for parsing codebases with hypothesis tests
|-- requirements.txt - package requirements
|-- main.py (explained in usage)
```

# Usage

`main.py` scrapes from the [dependency graph](https://github.com/HypothesisWorks/hypothesis/network/dependents) of the Hypothesis Github page. The dependents were pre-scraped (by me), and can be found in `dependents.json`. Takes a Github authorization token and an output destination.

```
usage: main.py [-h] --token TOKEN --output OUTPUT --mode {dependents,gh} [--stale-date STALE_DATE]
               [--timeout TIMEOUT]

Scrape from dependents

options:
  -h, --help            show this help message and exit
  --token TOKEN         GitHub token for authentication
  --output OUTPUT       Output file name (e.g., db.sqlite)
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

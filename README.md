# `fvspec`

Lean benchmark for real-world SWE tasks.

We scrape github for PBTs in `hypothesis` and use an LLM to transpile them to Lean specs, autoformalizing each function under test along the way.

## Repo

### `./leaderboard`

The website

### `./benchmark`

The synthetic data pipeline generating the eval. Requires `ANTHROPIC_API_KEY` in `.env`, requires `pbts_full.db` to be placed in `./benchmark/data`.

### `./baselines`

Conducting performance baselines on the benchmark

### Dependencies

All you need are `uv` and `elan` to work with the pipelines or evals, but `npm` is required for the website. Tip: run `lake build` in `./benchmark/lake-template` once to prepopulate the `.lake` dir for performance.

## Acknowledgements

This project is funded by the Advanced Research + Invention Agency (ARIA).

## License

This work is made available under both an MIT license and an Apache 2 license such that users can decide which to utilize.

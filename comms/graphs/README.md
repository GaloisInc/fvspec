# comms/graphs

Analysis code for all figures in the FVSpec paper.

## Structure

```
src/graphs/
  __init__.py   – FVSpec results figures (loads from HuggingFace: quinn-dougherty/fvspec)
  realpbt.py    – RealPBT corpus characterisation + PBT-vs-dependency analysis
                  (loads from benchmark/artifacts/realpbt2/pbts.jsonl
                   and  benchmark/artifacts/realpbt_deps.jsonl)
out/            – generated figures (gitignored)
```

## Usage

```bash
# Install dependencies (one-time)
uv sync

# Generate corpus characterisation figures only (no HF access needed)
make realpbt

# Generate results figures (requires HuggingFace login: huggingface-cli login)
make results

# Generate everything and copy into paper/figs/
make all
# or step by step:
make realpbt && make results && make install
```

## Figures produced

### Corpus characterisation (realpbt.py)

| Output file | Paper figure | Description |
|---|---|---|
| realpbt_pbts_per_repo | – | PBT count per repository |
| realpbt_stars_forks | – | Repository popularity |
| realpbt_licenses | – | License distribution |
| realpbt_complexity | – | PBT code complexity (LOC, CC, Halstead effort) |
| realpbt_pbt_vs_deps | fig:realpbt_pbt_vs_deps | PBT complexity vs. code under test |

### Results (__init__.py)

| Output file | Paper figure | Description |
|---|---|---|
| python_source | fig:python_source | Python source characteristics |
| structural_faithfulness | fig:structural_faithfulness | Structural faithfulness distribution |
| implementation_level | fig:implementation_level | Implementation level breakdown |
| lean_complexity | fig:lean_complexity | Lean output complexity |
| pipeline_cost | fig:pipeline_cost | Pipeline cost (time, tokens, turns) |
| difficulty_distribution | fig:difficulty_distribution | Difficulty split + grader confidence |
| difficulty_vs_faithfulness | fig:difficulty_vs_faithfulness | Difficulty vs. faithfulness / Lean size |

## Data requirements

| Script | Data source | Path |
|---|---|---|
| realpbt.py | RealPBT corpus | benchmark/artifacts/realpbt2/pbts.jsonl |
| realpbt.py | Dependency data | benchmark/artifacts/realpbt_deps.jsonl |
| __init__.py | FVSpec benchmark | HuggingFace: quinn-dougherty/fvspec |

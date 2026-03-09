# Baselines

Baseline implementations for measuring benchmark performance.

1. Load `quinn-dougherty/fvspec` from huggingface. 
2. Write a solver with `inspect-ai` that uses `lean-lsp-mcp` tools and the `lake-template` boilerplate dir in tmpdirs. 
3. Write outcome stats to `.toml` for automatic loading into `typst` in `./../comms/paper/*.typ`
4. The task is to actually write the proof-- to fill in the sorry in `Spec.lean`
5. pick 300 easys, 400 mediums, and 300 hards (based on haiku's difficulty estimate) based on ranseed fixing but otherwise shuffling uniformly within buckets. 
6. we will have `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `ANTHROPIC_API_KEY`. use inspect-ai primitives to make the parallelism as ergonomic as possible. notice that `.env` is in monorepo root, not in `./baselines`

## Structure

Currently minimal. Will contain:
- Baseline model implementations
- Evaluation scripts
- Comparison utilities

some pointers about project structure might be in `./../benchmark/AGENTS.md`. Especially:
- `pydantic.BaseModel` in dedicated `models.py` files.
- prompt loading from `.prompt` and `.prompt.template` plaintext files. 

## Development

```bash
uv sync  # Install dependencies
```

See root `AGENTS.md` for codestyle guidelines.

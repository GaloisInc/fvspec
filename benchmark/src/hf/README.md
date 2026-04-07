---
license: mit
task_categories:
- text-generation
tags:
- code
pretty_name: FVSpec
size_categories:
- 10K<n<100K
---

# `fvspec`

Based on [RealPBT](https://huggingface.co/datasets/Benchify/realpbt).

Scraping `hypothesis` property-based tests from the real world and transpiling them into Lean 4 challenge problems. Each sample pairs an `Impl.lean` (computable definitions) with a `Spec.lean` (theorem statements containing `sorry` for models to discharge).

THIS IS A ROUGH DRAFT SNEAK PEAK PLEASE DO NOT POST ANYWHERE. MORE SAMPLES AND MORE METRICS TO COME.

Browse the dataset at [fvspec.galois.com](https://fvspec.galois.com).

## TODO Usage

1. Place `lean-toolchain`, `lakefile.toml`, and `lake-manifest.json` from `benchmark/lake-template/` alongside the generated files.
2. Load via `datasets.load_dataset("quinn-dougherty/fvspec")`; concatenate `Spec.lean` after `Impl.lean` to form a single compilation unit.

## Acknowledgements

This project is funded by the Advanced Research + Invention Agency (ARIA).

## License

This work is made available under both an MIT license and an Apache 2 license such that users can decide which to utilize.

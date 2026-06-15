# FVSpec announcement thread

Style: standard ML-announcement thread, 8 tweets. Every tweet carries a hyperlink (arXiv / Hugging Face / site) or a figure. Post-ready images live in `comms/twitter/figs/` (PNG; vector PDF source kept alongside).

Links used:
- Paper: https://arxiv.org/abs/2606.01008
- PBT dataset: https://huggingface.co/datasets/GaloisInc/fvspec-pbt
- FV dataset: https://huggingface.co/datasets/GaloisInc/fvspec-fv
- Site / leaderboard: https://fvspec.galois.com

> Note: "Figure 1" in the paper = `fig:running-example` (the four artifacts of one FVSpec problem, in `sections/task.tex`). It's a TikZ diagram with no standalone PDF, so `figs/figure1_running_example.png` here was rendered (cropped) from page 4 of `neurips_2026.pdf`. The 3-agent pipeline diagram is Figure 5 (also TikZ).

---

**1/** 🧵
Formal specifications are hard to come by. Property based testing (PBT, roughly: declaring boundaries for fuzzers to search within) is considered a lightweight formal method. The PBT community (especially python's hypothesis) is therefore the largest corpus of specifications found on github.

🔗 Paper: arxiv.org/abs/2606.01008

---

**2/**
Introducing FVSpec: translating real-world PBTs into Lean challenges. We scrape github for hypothesis tests and "transpile" them (via LLM) to unproven Lean theorems, challenging future language models to complete the proofs.

🖼️ figs/figure1_running_example.png

---

**3/**
Why real-world tests? Synthetic coding puzzles leak into training data. We harvest 11,039 (deduplicated) Hypothesis PBTs straight from open-source Python repos written by real engineers. Contamination-resistant by construction.

🤗 huggingface.co/datasets/GaloisInc/fvspec-pbt

---

**4/**
The hard part is the translation: modeling Python semantics in Lean, inferring the *logical property* hidden inside an imperative test, and surviving dependently-typed programming in a rarely-seen language. A three-agent LLM pipeline turns 2,772 PBTs into 9,415 Lean specs (75,005 theorems).

🤗 huggingface.co/datasets/GaloisInc/fvspec-fv

---

**5/**
How good are the translations? We score every one on *structural faithfulness* — does the Lean spec preserve the params, types, Hypothesis strategies, assertions, and deps of the source PBT? The distribution modes above 0.5: most translations keep the essential structure.

🖼️ figs/structural_faithfulness.png

---

**6/**
Every sample is graded easy/hard by Claude Haiku 4.5 — predicting whether an agent could actually close the proof. The benchmark has a healthy mix of both, with the grader confident on most calls.

🖼️ figs/difficulty_distribution.png

---

**7/**
Baselines: GPT-5.4, Claude Opus 4.7, and Claude Sonnet 4.6 — each with the Lean LSP via MCP tools — on 100 easy + 100 hard problems. Best-of-5 proved rate: 67–73% easy, 43–59% hard (GPT-5.4 leads overall at 66%). 📈

🖼️ figs/baselines_prove_rate.png

---

**8/**
Everything is open: the scraper, the agent pipeline, both datasets, and a live leaderboard. AI is writing more and more of the world's code — FVSpec pushes on the underexplored problem of formally verifying it. Funded by @ARIA_research.

🔗 fvspec.galois.com · arxiv.org/abs/2606.01008

---

## Open questions before posting
- Tweet 1: arXiv link appended so it satisfies the "link or figure" rule — drop if you want a pure hook.
- Used the paper's 11,039 deduplicated PBT count (matches the figures), not the 21,746 raw rows on the HF card.
- `@ARIA_research` handle is a guess — verify before posting.
- Post-ready PNGs are in `figs/` (300 dpi, whitespace-trimmed); the `.pdf` vector sources are kept beside them.

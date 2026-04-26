GRAPHS_DIR := $(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
OUT_DIR     := $(GRAPHS_DIR)/out
FIGS_DIR    := $(GRAPHS_DIR)/../paper/figs

.PHONY: all graphs realpbt results install clean help

# Generate all graphs (FVSpec results + RealPBT dataset characterization)
graphs:
uv --directory $(GRAPHS_DIR) run graphs

## Generate all figures and install them into the paper
all: results realpbt install

## Generate FVSpec results figures (requires HuggingFace access)
results:
uv --directory $(GRAPHS_DIR) run graphs

## Generate RealPBT corpus characterization figures
realpbt:
uv --directory $(GRAPHS_DIR) run python -m graphs.realpbt

## Copy generated figures into comms/paper/figs/ for LaTeX
install: $(OUT_DIR)
mkdir -p $(FIGS_DIR)
cp $(OUT_DIR)/*.png $(FIGS_DIR)/

## Remove generated figures from out/
clean:
rm -f $(OUT_DIR)/*.png $(OUT_DIR)/*.pdf

help:
@echo "Targets:"
@echo "  all      - generate everything and install into paper/figs/"
@echo "  graphs   - run all graph subcommands via CLI"
@echo "  results  - FVSpec results figures (needs HF)"
@echo "  realpbt  - RealPBT corpus characterization figures"
@echo "  install  - copy out/*.png -> paper/figs/"
@echo "  clean    - remove out/*.png and out/*.pdf"

$(OUT_DIR):
mkdir -p $(OUT_DIR)

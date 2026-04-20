.PHONY: graphs realpbt clean

MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
OUT_DIR := $(MAKEFILE_DIR)out

# Generate all graphs (FVSpec results + RealPBT dataset characterization)
graphs:
	cd $(MAKEFILE_DIR) && uv run graphs

# Generate only RealPBT dataset characterization figures
realpbt:
	cd $(MAKEFILE_DIR) && uv run python -m graphs.realpbt

clean:
	rm -rf $(OUT_DIR)/*.png
	rm -rf $(OUT_DIR)/*.pdf

.PHONY: graphs realpbt clean

# Generate all graphs (FVSpec results + RealPBT dataset characterization)
graphs:
	cd /Users/maxvonhippel/projects/research/fvspec/comms/graphs && uv run graphs

# Generate only RealPBT dataset characterization figures
realpbt:
	cd /Users/maxvonhippel/projects/research/fvspec/comms/graphs && uv run python -m graphs.realpbt

clean:
	rm -rf /Users/maxvonhippel/projects/research/fvspec/comms/graphs/out/*.png
	rm -rf /Users/maxvonhippel/projects/research/fvspec/comms/graphs/out/*.pdf

PYTHON ?= python
SEASON ?= 2023

.PHONY: logos fetch-epa plot-epa refresh

logos:
$(PYTHON) -m scripts.download_logos --output-dir assets/logos --size 256

fetch-epa:
$(PYTHON) -m scripts.fetch_epa --season $(SEASON)

plot-epa:
$(PYTHON) -m scripts.plot_epa_scatter --season $(SEASON)

refresh: logos fetch-epa plot-epa

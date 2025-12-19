PYTHON ?= python
SEASON ?= 2023

.PHONY: logos fetch-epa plot-epa refresh

logos:
	($PYTHON) -m scripts.download_logos --output-dir assets/logos --size 256

fetch-epa:
	($PYTHON) -m scripts.fetch_epa --season $(SEASON) $(if $(WEEK_START),--week-start $(WEEK_START),) $(if $(WEEK_END),--week-end $(WEEK_END),) $(if $(MIN_WP),--min-wp $(MIN_WP),) $(if $(MAX_WP),--max-wp $(MAX_WP),) $(if $(INCLUDE_PLAYOFFS),--include-playoffs,)

plot-epa:
	($PYTHON) -m scripts.plot_epa_scatter --season $(SEASON) $(if $(WEEK_LABEL),--week "$(WEEK_LABEL)",) $(if $(INVERT_Y),--invert-y,)

refresh: logos fetch-epa plot-epa

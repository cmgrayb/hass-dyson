.PHONY: install test format

UV ?= uv

install:
	$(UV) sync --extra dev

test:
	$(UV) run --extra dev pytest tests

format:
	$(UV) run --extra dev ruff format .

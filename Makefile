.PHONY: install test format

init:
	@pip3 install uv

install: init
	uv sync --locked --extra dev

upgrade: init
	uv sync --upgrade --extra dev

test: install format
	uv run --locked --extra dev coverage erase
	uv run --locked --extra dev coverage run
	uv run --locked --extra dev coverage report

format:
	uv run --locked --extra dev ruff format .

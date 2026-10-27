.PHONY: install test lint clean

install:
	./install.sh

test:
	uv run pytest -v

lint:
	uv run ruff check
	uv run mypy src

clean:
	rm -rf .pytest_cache .ruff_cache

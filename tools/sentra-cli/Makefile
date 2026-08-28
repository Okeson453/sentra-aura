.PHONY: install test lint format types clean

install:
	poetry install

test:
	poetry run pytest tests/ -v

lint:
	poetry run ruff check src/ tests/
	poetry run mypy src/

format:
	poetry run ruff format src/ tests/

types:
	poetry run mypy src/

clean:
	rm -rf dist/ .pytest_cache/ .mypy_cache/

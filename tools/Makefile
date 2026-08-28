.PHONY: install test lint format types clean

install:
	poetry install

test:
	poetry run pytest packages/ services/ tools/ -v

lint:
	poetry run ruff check packages/ services/ tools/
	poetry run mypy packages/ services/

format:
	poetry run ruff format packages/ services/ tools/

types:
	poetry run mypy packages/ services/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.mypy_cache' -exec rm -rf {} + 2>/dev/null || true

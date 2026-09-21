.PHONY: install generate lint typecheck test test-ocr audit build compose-groq compose-ollama down

install:
	uv sync --extra dev

generate:
	uv run python scripts/generate_demo_data.py

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run pyright

test:
	uv run pytest -m "not ocr and not live" --cov=clinical_screening

test-ocr:
	uv sync --extra dev --extra ocr
	uv run pytest -m ocr

audit:
	uv run pip-audit

build:
	uv build

compose-groq:
	SCREENING_PROVIDER=groq docker compose up --build

compose-ollama:
	SCREENING_PROVIDER=ollama docker compose --profile ollama up --build

down:
	docker compose --profile ollama down

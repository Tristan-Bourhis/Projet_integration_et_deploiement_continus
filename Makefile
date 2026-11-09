PYTHON ?= .venv/bin/python
CLI = .venv/bin/transaction-pipeline

.PHONY: install test lint local up run process report integration demo down
install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements-dev.lock
	.venv/bin/pip install --no-deps -e .
test:
	$(PYTHON) -m pytest -m 'not services' --cov=transaction_pipeline --cov-report=term-missing
lint:
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .
local:
	$(CLI) run
up:
	docker compose up -d --wait postgres s3
run: up
	docker compose run --build --rm pipeline run --source s3
process:
	docker compose run --rm pipeline process --source s3
report:
	docker compose run --rm pipeline report
integration: up
	$(PYTHON) scripts/integration.py
demo:
	$(PYTHON) scripts/demo_failure.py
down:
	docker compose down

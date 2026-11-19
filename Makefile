.PHONY: help install lint security test run docker-build docker-up docker-down clean

PYTHON ?= python
PIP ?= pip

help:
	@echo "OpsPulse DevOps Automation Commands:"
	@echo "  make install       Install all project dependencies"
	@echo "  make lint          Run flake8 code style checks"
	@echo "  make security      Run Bandit security audit"
	@echo "  make test          Run unit and integration tests"
	@echo "  make run           Run OpsPulse locally on port 8000"
	@echo "  make docker-build  Build production Docker image"
	@echo "  make docker-up     Start entire stack with Docker Compose"
	@echo "  make docker-down   Stop Docker Compose stack"
	@echo "  make clean         Clean cache and temporary files"

install:
	$(PIP) install -r requirements-dev.txt

lint:
	flake8 src tests --max-line-length=120

security:
	bandit -r src/

test:
	pytest -v

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

docker-build:
	docker build -t opspulse-sentinel:latest .

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -rf .coverage htmlcov

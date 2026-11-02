# -include .env
# export GROQ_API_KEY
-include .env

export GROQ_API_KEY

VENV := venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
ALEMBIC := $(VENV)/bin/alembic
PYTEST := $(VENV)/bin/pytest

.PHONY: help install run reload migrate migration test upgrade freeze up-docker down-docker restart-docker clean

help:
	@echo "Available commands:"
	@echo "  make install        - Create venv and install dependencies"
	@echo "  make run            - Run FastAPI server"
	@echo "  make reload         - Run FastAPI server with auto-reload"
	@echo "  make migrate        - Apply Alembic migrations (upgrade head)"
	@echo "  make migration m=.. - Create a new Alembic migration"
	@echo "  make test           - Run pytest test suite"
	@echo "  make up-docker      - Start Docker services (PostgreSQL)"
	@echo "  make down-docker    - Stop Docker services"
	@echo "  make restart-docker - Restart Docker services"
	@echo "  make freeze         - Update requirements.txt from venv"
	@echo "  make upgrade        - Upgrade pip and installed packages"
	@echo "  make clean          - Remove caches and temporary files"

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

run:
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000

reload:
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --reload

migrate:
	$(ALEMBIC) upgrade head

migration:
	@if [ -z "$(m)" ]; then \
		$(ALEMBIC) revision --autogenerate -m "auto_migration"; \
	else \
		$(ALEMBIC) revision --autogenerate -m "$(m)"; \
	fi

test:
	$(PYTEST) -v

upgrade:
	$(PIP) install --upgrade pip
	$(PIP) install --upgrade -r requirements.txt

freeze:
	$(PIP) freeze > requirements.txt

up-docker:
	docker compose up -d

down-docker:
	docker compose down

restart-docker: down-docker up-docker

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

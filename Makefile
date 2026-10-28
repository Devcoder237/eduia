# Commandes courantes. `make help` pour la liste.
.DEFAULT_GOAL := help
BACKEND := backend
FRONTEND := frontend

help: ## Affiche cette aide
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Installe les dépendances (backend + frontend)
	cd $(BACKEND) && python -m pip install -r requirements-dev.txt
	cd $(FRONTEND) && npm install

lint: ## Ruff (backend) + TypeScript (frontend)
	cd $(BACKEND) && ruff check . && ruff format --check .
	cd $(FRONTEND) && npm run typecheck

test: ## Tests backend (pytest) et frontend (vitest)
	cd $(BACKEND) && python -m pytest --cov=app --cov-report=term-missing
	cd $(FRONTEND) && npm test

audit: ## Audit des dépendances (pip-audit + npm audit)
	cd $(BACKEND) && pip-audit -r requirements.txt
	cd $(FRONTEND) && npm audit --omit=dev --audit-level=high

migrate: ## Applique les migrations Alembic (DATABASE_URL requis)
	cd $(BACKEND) && alembic upgrade head

migration: ## Crée une migration : make migration m="message"
	cd $(BACKEND) && alembic revision --autogenerate -m "$(m)"

dev-api: ## API en local avec rechargement
	cd $(BACKEND) && uvicorn app.main:app --reload --port 8000

dev-web: ## Front Vite en local
	cd $(FRONTEND) && npm run dev

secret: ## Génère une SECRET_KEY
	python $(BACKEND)/scripts/generate_secret.py

up: ## Lance PostgreSQL + API + front via Docker
	docker compose up --build

down: ## Arrête les conteneurs
	docker compose down

docker-build: ## Construit l'image de production
	docker build -t eduia-api:local $(BACKEND)

.PHONY: help install lint test audit migrate migration dev-api dev-web secret up down docker-build

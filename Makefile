.PHONY: run api worker fmt lint type test cov migrate upgrade heads seed docker-up docker-down docker-build docker-logs docker-shell

# Development server
run:
	uvicorn app.main:app --reload

api: run

# Celery worker
worker:
	celery -A app.workers.celery_app worker --loglevel=INFO --pool=solo

# Code formatting and linting
fmt:
	ruff check . --fix

lint:
	ruff check .

type:
	mypy app

# Testing
test:
	pytest -q

test-verbose:
	pytest -v

test-cov:
	pytest --cov=app -q

test-unit:
	pytest -m unit -q

test-integration:
	pytest -m integration -q

test-e2e:
	pytest -m e2e -q

test-fast:
	pytest -m "not slow" -q

test-slow:
	pytest -m slow -q

test-redis:
	pytest -m redis -q

test-auth:
	pytest -m auth -q

test-appointments:
	pytest -m appointments -q

test-availability:
	pytest -m availability -q

test-coverage:
	pytest --cov=app --cov-report=html --cov-report=term-missing -q

test-coverage-xml:
	pytest --cov=app --cov-report=xml -q

test-all:
	pytest -q && mypy app

test-ci:
	pytest --maxfail=1 --disable-warnings -q --cov=app --cov-report=xml

# Database migrations
migrate:
	alembic revision --autogenerate -m "auto"

upgrade:
	alembic upgrade head

heads:
	alembic heads

# Data seeding
seed:
	python -m app.scripts.seed

# Docker commands
docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-build:
	docker compose build

docker-logs:
	docker compose logs -f

docker-shell:
	docker compose exec api bash

# Docker database commands
docker-migrate:
	docker compose exec api alembic revision --autogenerate -m "auto"

docker-upgrade:
	docker compose exec api alembic upgrade head

docker-seed:
	docker compose exec api python -m app.scripts.seed

# Docker testing
docker-test:
	docker compose exec api pytest -q

docker-test-verbose:
	docker compose exec api pytest -v

# Production commands
prod-up:
	docker-compose -f docker-compose.production.yml up -d

prod-down:
	docker-compose -f docker-compose.production.yml down

prod-build:
	docker-compose -f docker-compose.production.yml build

prod-logs:
	docker-compose -f docker-compose.production.yml logs -f

prod-shell:
	docker-compose -f docker-compose.production.yml exec api bash

# Production database commands
prod-migrate:
	docker-compose -f docker-compose.production.yml exec api alembic revision --autogenerate -m "auto"

prod-upgrade:
	docker-compose -f docker-compose.production.yml exec api alembic upgrade head

prod-seed:
	docker-compose -f docker-compose.production.yml exec api python -m app.scripts.seed

# Production monitoring
prod-status:
	docker-compose -f docker-compose.production.yml ps

prod-health:
	curl -f http://localhost:8000/health || echo "Health check failed"

prod-metrics:
	curl -f http://localhost:8000/metrics || echo "Metrics not available"

# Backup and recovery
backup:
	python scripts/backup.py --action backup --type full

backup-db:
	python scripts/backup.py --action backup --type database

backup-files:
	python scripts/backup.py --action backup --type files

backup-config:
	python scripts/backup.py --action backup --type config

backup-list:
	python scripts/backup.py --action list

restore-db:
	python scripts/backup.py --action restore --backup-file $(BACKUP_FILE) --type database

restore-files:
	python scripts/backup.py --action restore --backup-file $(BACKUP_FILE) --type files

# System administration
install-deps:
	pip install -r requirements.txt

install-dev-deps:
	pip install -r requirements-dev.txt

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov
	rm -rf dist
	rm -rf build

clean-docker:
	docker system prune -f
	docker volume prune -f

# Security
security-scan:
	python -m safety check
	python -m bandit -r app/

# Performance testing
perf-test:
	python -m locust -f tests/performance/locustfile.py --host=http://localhost:8000

# Documentation
docs:
	python -m mkdocs serve

docs-build:
	python -m mkdocs build

# Deployment
deploy-staging:
	./scripts/deploy.sh staging

deploy-production:
	./scripts/deploy.sh production

# Monitoring
monitor-logs:
	tail -f /var/log/healthcare-api/*.log

monitor-system:
	htop

monitor-db:
	psql -h localhost -U healthcare_user -d healthcare_scheduling -c "SELECT * FROM pg_stat_activity;"

monitor-redis:
	redis-cli monitor

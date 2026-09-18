.PHONY: venv install run worker test lint typecheck security audit translations cyberhero-install cyberhero-build cyberhero-dev seed migrate ci

PY ?= .venv/bin/python
PIP ?= .venv/bin/pip
FLASK ?= .venv/bin/flask --app wsgi:app

venv:
	python3.12 -m venv .venv && $(PIP) install -U pip

install: venv
	$(PIP) install -r requirements-dev.txt

run:
	$(FLASK) run --debug --port 8000

worker:
	.venv/bin/celery -A app.celery_worker:celery worker --loglevel=INFO

migrate:
	$(FLASK) db upgrade

seed:
	$(FLASK) seed-roles && $(FLASK) seed-demo && $(FLASK) seed-cyberhero

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check . && .venv/bin/ruff format --check .

typecheck:
	.venv/bin/mypy

security:
	.venv/bin/bandit -c pyproject.toml -r app -q

audit:
	.venv/bin/pip-audit -r requirements.txt

translations:
	.venv/bin/pybabel extract -F babel.cfg -k _l -o app/translations/messages.pot app
	.venv/bin/pybabel update -i app/translations/messages.pot -d app/translations
	.venv/bin/pybabel compile -d app/translations -f

cyberhero-install:
	cd cyberhero && npm ci

cyberhero-build:
	cd cyberhero && npm run build

cyberhero-dev:
	cd cyberhero && npm run dev

ci: lint typecheck security test cyberhero-build

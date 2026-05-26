# IRIS development Makefile.
#
# Every target listed in T004 returns zero today. The bodies of `lint`,
# `typecheck`, `test-cov`, `dev`, `up`, and `down` are intentionally thin
# until T005 (pytest + coverage), T006 (ruff + mypy), and T007 (compose
# + API runner) land, at which point the recipes grow to call the real
# tools. The structure here is the contract those tasks plug into.

UV ?= uv
RUN ?= $(UV) run
COMPOSE_FILE := compose.dev.yaml

.DEFAULT_GOAL := help
.PHONY: help install dev up down lint typecheck test test-cov clean

help:
	@echo "IRIS Makefile targets:"
	@echo "  install     sync all workspace packages into .venv"
	@echo "  dev         start the dev API (wired by T007)"
	@echo "  up          bring up dev compose services (wired by T007)"
	@echo "  down        tear down dev compose services (wired by T007)"
	@echo "  lint        run import-linter (ruff added by T006)"
	@echo "  typecheck   run mypy --strict (wired by T006)"
	@echo "  test        run pytest with default markers"
	@echo "  test-cov    run pytest with coverage report (wired by T005)"
	@echo "  clean       remove caches and build artifacts"

install:
	$(UV) sync --all-packages

dev:
	@if [ -f $(COMPOSE_FILE) ]; then \
		echo "make dev: API runner lands with T007. Use 'make up' for services."; \
	else \
		echo "make dev: not yet wired (T007 adds $(COMPOSE_FILE) and the API runner)."; \
	fi

up:
	@if [ -f $(COMPOSE_FILE) ]; then \
		docker compose -f $(COMPOSE_FILE) up -d; \
	else \
		echo "make up: $(COMPOSE_FILE) lands with T007."; \
	fi

down:
	@if [ -f $(COMPOSE_FILE) ]; then \
		docker compose -f $(COMPOSE_FILE) down; \
	else \
		echo "make down: $(COMPOSE_FILE) lands with T007."; \
	fi

lint:
	$(RUN) lint-imports

typecheck:
	@echo "make typecheck: wired by T006 (mypy --strict on iris-engine and adapters)."

test:
	$(RUN) pytest

test-cov:
	@echo "make test-cov: wired by T005 (coverage threshold 80% on iris-engine)."

clean:
	find . -type d \( \
		-name __pycache__ -o \
		-name .pytest_cache -o \
		-name .ruff_cache -o \
		-name .mypy_cache -o \
		-name .import_linter_cache -o \
		-name htmlcov -o \
		-name '*.egg-info' \
	\) -not -path './.venv/*' -prune -exec rm -rf {} +
	rm -f .coverage

# IRIS development Makefile.
#
# T004 established the nine targets. T005 wires test-cov. T006 wires
# lint (ruff + import-linter) and typecheck (mypy). T007 will wire dev/up/down.
#
# Targets that call uv work on every OS without adaptation.
# dev/up/down/clean are OS-specific and live inside the ifeq block below.

UV ?= uv
RUN ?= $(UV) run
COMPOSE_FILE := compose.dev.yaml
ADAPTER_SRCS := $(wildcard packages/iris-adapters/*/src)
INSTALL_STAMP := .venv/.install-stamp

.DEFAULT_GOAL := help
.PHONY: help install dev up down lint typecheck test test-cov clean pre-commit-install

# ── shared targets (bash + Windows) ─────────────────────────────────────────

help:
	@echo "IRIS Makefile targets:"
	@echo "  install              sync all workspace packages into .venv"
	@echo "  dev                  start the API at http://localhost:8088 (needs compose.dev.yaml)"
	@echo "  up                   start Postgres and Redis dev services"
	@echo "  down                 stop Postgres and Redis dev services"
	@echo "  lint                 ruff check + import-linter architecture contracts"
	@echo "  typecheck            mypy --strict on iris-engine and all adapters"
	@echo "  test                 pytest (contract and integration markers included; e2e excluded)"
	@echo "  test-cov             pytest with branch coverage; HTML report in htmlcov/"
	@echo "  clean                remove __pycache__, .pytest_cache, htmlcov, .coverage, etc."
	@echo "  pre-commit-install   install pre-commit hooks into .git/hooks/"

install:
	$(UV) sync --all-packages
	@$(UV) run python -c "from pathlib import Path; Path('$(INSTALL_STAMP)').touch()"

# Rebuilt automatically whenever pyproject.toml or uv.lock changes.
# Dependent targets list this as a prerequisite so the workspace is always
# populated before they run, even on a fresh clone.
$(INSTALL_STAMP): pyproject.toml uv.lock
	@echo ""
	@echo "==> Prerequisite: workspace packages are not installed or are out of date."
	@echo "==> Running: uv sync --all-packages"
	@echo ""
	$(UV) sync --all-packages
	@$(UV) run python -c "from pathlib import Path; Path('$@').touch()"
	@echo ""
	@echo "==> Installation complete. Proceeding with the requested target."
	@echo ""

pre-commit-install:
	$(RUN) pre-commit install

lint: $(INSTALL_STAMP)
	$(RUN) ruff check .
	$(RUN) lint-imports

typecheck: $(INSTALL_STAMP)
	$(RUN) mypy packages/iris-engine/src $(ADAPTER_SRCS)

test: $(INSTALL_STAMP)
	$(RUN) pytest

test-cov: $(INSTALL_STAMP)
	$(RUN) pytest --cov=iris_engine --cov-report=html --cov-report=term-missing --cov-fail-under=80

# ── OS-specific targets ──────────────────────────────────────────────────────

ifeq ($(OS),Windows_NT)

dev: $(INSTALL_STAMP)
	$(RUN) uvicorn iris_api.main:app --host 0.0.0.0 --port 8088 --reload

up:
	@powershell -NoProfile -Command \
	  "if(Test-Path '$(COMPOSE_FILE)'){ \
	       docker compose -f $(COMPOSE_FILE) up -d \
	   }else{ \
	       Write-Host 'make up: $(COMPOSE_FILE) lands with T007.' \
	   }"

down:
	@powershell -NoProfile -Command \
	  "if(Test-Path '$(COMPOSE_FILE)'){ \
	       docker compose -f $(COMPOSE_FILE) down \
	   }else{ \
	       Write-Host 'make down: $(COMPOSE_FILE) lands with T007.' \
	   }"

clean:
	@powershell -NoProfile -ExecutionPolicy Bypass -Command \
	  "$$names='__pycache__','.pytest_cache','.ruff_cache','.mypy_cache', \
	         '.import_linter_cache','htmlcov'; \
	   $$dirs=Get-ChildItem -Recurse -Directory \
	     | Where-Object{$$names -contains $$_.Name -or $$_.Name -like '*.egg-info'} \
	     | Where-Object{-not $$_.FullName.Contains('.venv')} \
	     | Sort-Object{$$_.FullName.Length} -Descending; \
	   $$cov=Test-Path '.coverage'; \
	   $$stamp=Test-Path '$(INSTALL_STAMP)'; \
	   if($$dirs -or $$cov -or $$stamp){ \
	       Write-Host 'Following files have been cleared:'; \
	       foreach($$d in $$dirs){ \
	           Write-Host('  '+$$d.FullName); \
	           Remove-Item -Recurse -Force $$d.FullName -ErrorAction SilentlyContinue \
	       }; \
	       if($$cov){Write-Host '  .coverage'; Remove-Item -Force '.coverage'}; \
	       if($$stamp){Write-Host '  $(INSTALL_STAMP)'; Remove-Item -Force '$(INSTALL_STAMP)'} \
	   }else{Write-Host 'Environment is clean.'}"

else

dev: $(INSTALL_STAMP)
	$(RUN) uvicorn iris_api.main:app --host 0.0.0.0 --port 8088 --reload

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

clean:
	@cleared=0; \
	for d in $$(find . -type d \( \
	    -name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' -o \
	    -name '.mypy_cache' -o -name '.import_linter_cache' -o -name 'htmlcov' -o \
	    -name '*.egg-info' \) -not -path './.venv/*' -prune 2>/dev/null); do \
	  if [ "$$cleared" -eq 0 ]; then echo "Following files have been cleared:"; fi; \
	  echo "  $$d"; rm -rf "$$d"; cleared=1; \
	done; \
	if [ -f .coverage ]; then \
	  if [ "$$cleared" -eq 0 ]; then echo "Following files have been cleared:"; fi; \
	  echo "  .coverage"; rm -f .coverage; cleared=1; \
	fi; \
	if [ -f $(INSTALL_STAMP) ]; then \
	  if [ "$$cleared" -eq 0 ]; then echo "Following files have been cleared:"; fi; \
	  echo "  $(INSTALL_STAMP)"; rm -f $(INSTALL_STAMP); cleared=1; \
	fi; \
	if [ "$$cleared" -eq 0 ]; then echo "Environment is clean."; fi

endif

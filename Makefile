# IRIS development Makefile.
#
# T004 established the nine targets. T005 wires test-cov. T006 wires
# lint (ruff + import-linter) and typecheck (mypy). T007 wired dev/up/down.
# distclean and status are convenience extras outside the sprint-0 task scope.
#
# Targets that call uv work on every OS without adaptation.
# dev/up/down/clean/distclean/status are OS-specific and live in the ifeq block.

UV ?= uv
RUN ?= $(UV) run
COMPOSE_FILE := compose.dev.yaml
ADAPTER_SRCS := $(wildcard packages/iris-adapters/*/src)
INSTALL_STAMP := .venv/.install-stamp

.DEFAULT_GOAL := help
.PHONY: help install dev up down lint typecheck test test-cov clean distclean status

# ── shared targets (bash + Windows) ─────────────────────────────────────────

help:
	@echo "IRIS Makefile targets:"
	@echo "  install     sync all workspace packages into .venv"
	@echo "  dev         start the API at http://localhost:8088 (needs compose.dev.yaml)"
	@echo "  up          start Postgres and Redis dev services"
	@echo "  down        stop Postgres and Redis dev services"
	@echo "  lint        ruff check + import-linter architecture contracts"
	@echo "  typecheck   mypy --strict on iris-engine and all adapters"
	@echo "  test        pytest (contract and integration markers included; e2e excluded)"
	@echo "  test-cov    pytest with branch coverage; HTML report in htmlcov/"
	@echo "  clean       remove __pycache__, .pytest_cache, htmlcov, .coverage, etc."
	@echo "  distclean   clean + remove .venv, Docker volumes, and uv cache"
	@echo "  status      show git state, venv, Docker service health, and port usage"

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

distclean: clean
	@powershell -NoProfile -Command \
	  "$$pid = (Get-NetTCPConnection -LocalPort 8088 -State Listen -ErrorAction SilentlyContinue).OwningProcess; \
	   if($$pid){ Write-Host '==> Stopping API server on :8088 ...'; Stop-Process -Id $$pid -Force -ErrorAction SilentlyContinue }"
	@powershell -NoProfile -ExecutionPolicy Bypass -Command \
	  "Write-Host '==> Removing .venv ...'; \
	   Remove-Item -Recurse -Force '.venv' -ErrorAction SilentlyContinue; \
	   Write-Host '==> Wiping Docker volumes ...';"
	@powershell -NoProfile -Command \
	  "if(Test-Path '$(COMPOSE_FILE)'){ \
	       docker compose -f $(COMPOSE_FILE) down -v \
	   }else{ \
	       Write-Host '  ($(COMPOSE_FILE) not found; skipping)' \
	   }"
	$(UV) cache clean
	@powershell -NoProfile -Command "Write-Host '==> distclean complete.'"

status:
	@powershell -NoProfile -ExecutionPolicy Bypass -Command \
	  "$$branch = git branch --show-current 2>$$null; if(-not $$branch){ $$branch='(unknown)' }; \
	   $$dirty  = (git status --porcelain 2>$$null | Measure-Object -Line).Lines; \

	   Write-Host ''; \
	   Write-Host 'IRIS Dev Environment Status'; \
	   Write-Host '==========================='; \
	   Write-Host ''; \
	   Write-Host 'Git'; \
	   Write-Host ('  branch    : ' + $$branch); \
	   if($$dirty -eq 0){ Write-Host '  tree      : clean' } \
	   else{ Write-Host ('  tree      : ' + $$dirty + ' file(s) modified -- run: git status') }; \
	   Write-Host ''; \
	   Write-Host 'Python'; \
	   if(Test-Path '.venv'){ \
	       $$count = ($(UV) pip list 2>$$null | Select-Object -Skip 2 | Measure-Object -Line).Lines; \
	       Write-Host ('  .venv     : present  (' + $$count + ' packages)') \
	   }else{ Write-Host '  .venv     : absent -- run: make install' }; \
	   Write-Host ''; \
	   Write-Host 'Docker Services  ($(COMPOSE_FILE))'; \
	   if(Test-Path '$(COMPOSE_FILE)'){ \
	       if(Get-Command docker -ErrorAction SilentlyContinue){ \
	           try{ docker compose -f $(COMPOSE_FILE) ps } catch { Write-Host '  (docker unavailable)' } \
	       }else{ Write-Host '  (docker unavailable)' } \
	   }else{ \
	       Write-Host '  $(COMPOSE_FILE) not found' \
	   }; \

	   Write-Host ''; \
	   Write-Host 'Dev Ports'; \
	   $$listeners = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners(); \
	   $$portMap = @{5488='Postgres'; 6399='Redis'; 8088='API'}; \
	   foreach($$port in @(5488, 6399, 8088)){ \
	       $$label = $$portMap[$$port]; \
	       $$state = if($$listeners | Where-Object { $$_.Port -eq $$port }){'in use'}else{'free'}; \
	       Write-Host ('  :' + $$port + '  ' + ('(' + $$label + ')').PadRight(10) + '  ' + $$state) \
	   }; \

	   Write-Host ''"

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

distclean: clean
	@if lsof -i :8088 -sTCP:LISTEN -t >/dev/null 2>&1; then \
		echo "==> Stopping API server on :8088 ..."; \
		kill $$(lsof -ti :8088 -sTCP:LISTEN) 2>/dev/null || true; \
		sleep 1; \
	fi
	@echo "==> Removing .venv ..."
	@rm -rf .venv
	@echo "==> Wiping Docker volumes ..."
	@if [ -f $(COMPOSE_FILE) ]; then \
		docker compose -f $(COMPOSE_FILE) down -v; \
	else \
		echo "  ($(COMPOSE_FILE) not found; skipping)"; \
	fi
	@echo "==> Clearing uv cache ..."
	@$(UV) cache clean
	@echo "==> distclean complete."

status:
	@echo ""
	@echo "IRIS Dev Environment Status"
	@echo "==========================="
	@echo ""
	@echo "Git"
	@printf "  %-10s %s\n" "branch:" "$$(git branch --show-current 2>/dev/null || echo '(unknown)')"
	@dirty=$$(git status --porcelain 2>/dev/null | wc -l | tr -d ' '); \
	 if [ "$$dirty" -eq 0 ]; then \
	   printf "  %-10s %s\n" "tree:" "clean"; \
	 else \
	   printf "  %-10s %s\n" "tree:" "$$dirty file(s) modified -- run: git status"; \
	 fi
	@echo ""
	@echo "Python"
	@if [ -d .venv ]; then \
		count=$$($(UV) pip list 2>/dev/null | tail -n +3 | wc -l | tr -d ' '); \
		printf "  %-10s %s\n" ".venv:" "present  ($$count packages)"; \
	else \
		printf "  %-10s %s\n" ".venv:" "absent -- run: make install"; \
	fi
	@echo ""
	@echo "Docker Services  ($(COMPOSE_FILE))"
	@if [ -f $(COMPOSE_FILE) ]; then \
		docker compose -f $(COMPOSE_FILE) ps 2>/dev/null || echo "  (docker unavailable)"; \
	else \
		echo "  ($(COMPOSE_FILE) not found)"; \
	fi
	@echo ""
	@echo "Dev Ports"
	@for entry in "5488:Postgres" "6399:Redis" "8088:API"; do \
		port=$$(echo "$$entry" | cut -d: -f1); \
		label=$$(echo "$$entry" | cut -d: -f2); \
		if lsof -i :$$port -sTCP:LISTEN -t >/dev/null 2>&1; then \
			state="in use"; \
		else \
			state="free"; \
		fi; \
		printf "  :%-6s %-10s %s\n" "$$port" "($$label)" "$$state"; \
	done
	@echo ""

endif

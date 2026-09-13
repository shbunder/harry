# Harry — the commands. `make` on its own lists them.
#
# Prefer a make target over the bare command: the targets encode the right
# interpreter, the right flags, and the lock the gate needs.
#
# What make deliberately does NOT do is read `.env` or `.env.local`. `harry/config.py`
# is the only reader, which is what keeps `.env.local` winning over `.env` and a real
# environment variable winning over both. Make loading them would also break on the
# first value containing a `#` — `SLACK_DEFAULT_CHANNEL=#harry` already is one.
#
# There is no CI, by choice. `make check` before you finish is the only thing
# between a change and main.

.DEFAULT_GOAL := help
SHELL := /bin/bash

UV      := uv
PY      := $(UV) run python
BOARD   := $(PY) project/board.py

# The gitignored files a fresh worktree needs, because git will not bring them. Keep
# this list honest: a worktree missing one of these fails in a way that looks like a
# code problem. Everything tracked arrives with the checkout and must not be listed.
SEED    := .env.local

# One gate at a time. Two suites on one machine is how a failure neither run can
# reproduce alone appears. `mkdir` is the atomic part; the trap is what releases it.
LOCK    := .claude/.gate.lock

GREEN := \033[32m
WARN  := \033[33m⚠\033[0m
DIM   := \033[2m
OFF   := \033[0m

.PHONY: help env-install check lint format typecheck test test-cov lock env-template \
        board lanes lessons worktree worktree-prune probe spike serve digest-dry digest-now \
        image up down logs docs clean

help:  ## Show this help
	@echo ""
	@echo "  Harry — Claude thinks, Harry does."
	@echo ""
	@grep -hE '^[a-z][a-z0-9-]*:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

env-install:  ## Install the workspace and the dev tools
	$(UV) sync --all-packages
	@echo -e "$(DIM)Tier-2 article fetching also needs a browser: make browser$(OFF)"

browser:  ## Install the Chromium that tier-2 article fetching drives
	$(UV) run playwright install chromium

env-template:  ## Write each capability's committed .env from its declaration. ARGS=--check to verify.
	$(PY) scripts/env_template.py $(ARGS)

lock:  ## Re-resolve the lockfile
	$(UV) lock

# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

check:  ## THE GATE: format, lint, typecheck, covered tests. Run before you finish.
	@mkdir $(LOCK) 2>/dev/null || { \
	  echo -e "$(WARN) The gate is already running (held since $$(stat -f %Sm $(LOCK) 2>/dev/null || echo '?'))."; \
	  echo "   Wait for it, or remove $(LOCK) if that run is dead."; exit 1; }
	@trap 'rmdir $(LOCK) 2>/dev/null || true' EXIT; \
	  $(MAKE) --no-print-directory format lint typecheck test-cov
	@echo -e "$(GREEN)✓ gate green$(OFF)"

format:  ## Format Python in place
	$(UV) run ruff format .

lint:  ## Lints, import sorting, and the two repo guards — no fixing
	$(UV) run ruff format --check .
	$(UV) run ruff check .
	$(PY) scripts/check_no_board_refs.py
	$(PY) scripts/check_capabilities.py
	$(PY) scripts/env_template.py --check

typecheck:  ## Run pyright over the workspace
	$(UV) run pyright

test:  ## Run the suite, no coverage gate. Skips anything marked `live`.
	$(UV) run pytest -m "not live" $(ARGS)

test-cov:  ## Run the suite under the coverage floor
	$(UV) run coverage run -m pytest -m "not live"
	$(UV) run coverage report

test-live:  ## Run the tests that reach a real external service. Never part of the gate.
	$(UV) run pytest -m live $(ARGS)

# ---------------------------------------------------------------------------
# The board
# ---------------------------------------------------------------------------

board:  ## List the board. Usage: make board [ARGS="stories --feature FEAT-..."]
	@$(BOARD) list $(ARGS)

lanes:  ## What is in flight, what has a branch, and what collides
	@$(BOARD) lanes

lessons:  ## Search lessons learned. Usage: make lessons Q="remarkable push"
	@if [ -z "$(Q)" ]; then echo -e "$(WARN) Usage: make lessons Q=\"<keywords>\""; exit 1; fi
	@$(PY) scripts/query_lessons.py $(Q)

worktree:  ## Start a feature: check the gates, branch, and open its worktree. FEAT=… SLUG=… [FORCE=1]
	@if [ -z "$(FEAT)" ] || [ -z "$(SLUG)" ]; then \
	  echo -e "$(WARN) Usage: make worktree FEAT=FEAT-260912-a1b2c3 SLUG=the-slug"; exit 1; fi
	@$(BOARD) can-start $(FEAT)$(if $(FORCE), --force,) || exit 1
	@SHORT=$$(echo "$(FEAT)" | rev | cut -d- -f1 | rev); \
	 DIR=.claude/worktrees/$$SHORT; \
	 SLOT=$$(( ( $$(ls -1 .claude/worktrees 2>/dev/null | wc -l) ) + 1 )); \
	 git worktree add "$$DIR" -b feat/$(FEAT)-$(SLUG); \
	 for f in $(SEED); do [ -f "$$f" ] && cp "$$f" "$$DIR/$$f" && echo "  seeded $$f"; done; \
	 printf '\n# Written by `make worktree`. This tree gets its own port and its own\n# data directory, so a second stack does not kill the first.\nHARRY_PORT=%s\nHARRY_DATA_DIR=%s\n' \
	   "$$((7430 + $$SLOT))" "$$PWD/$$DIR/data" >> "$$DIR/.env.local"; \
	 echo ""; \
	 echo "  worktree: $$DIR"; \
	 echo "  port:     $$((7430 + $$SLOT))   data: $$DIR/data"; \
	 echo "  Tracked files came with the checkout; only the gitignored ones are seeded."; \
	 echo "  The branch is what makes this In Progress — there is no status to set."; 

worktree-prune:  ## Drop worktree registrations whose directory is gone
	git worktree prune -v

# ---------------------------------------------------------------------------
# Running Harry
# ---------------------------------------------------------------------------

probe:  ## The MCP probe: can a client reach Harry? Usage: make probe [ARGS="call --ping"]
	$(PY) scripts/mcp_probe.py $(or $(ARGS),serve)

spike:  ## Run a Phase 0 spike. Usage: make spike S=remarkable-push
	@if [ -z "$(S)" ]; then ls -1 scratch/*.py 2>/dev/null | sed 's|scratch/||;s|\.py$$||;s|^|  |' \
	  || echo "  (no spikes yet — see /spike)"; exit 0; fi
	$(PY) scratch/$(S).py $(ARGS)

serve:  ## Run Harry natively, on whatever port .env/.env.local resolve to
	$(PY) -m harry --reload

digest-dry:  ## Build today's page to out/digest.pdf without pushing it
	$(PY) -m harry.modules.digest --dry-run --out out/digest.pdf
	@command -v open >/dev/null && open out/digest.pdf || true

digest-now:  ## Build today's page and push it to the tablet
	$(PY) -m harry.modules.digest --push

# ---------------------------------------------------------------------------
# The container
# ---------------------------------------------------------------------------

image:  ## Build Harry's image
	docker build -t harry:latest .

up:  ## Start Harry with compose
	docker compose up -d

down:  ## Stop Harry
	docker compose down

logs:  ## Follow Harry's logs
	docker compose logs -f harry

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

clean:  ## Remove caches and build output
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov out build dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

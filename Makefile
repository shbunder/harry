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
        board lanes lessons worktree worktree-prune probe spike serve digest-dry digest-candidates remarkable-pair \
        image up down logs health up-dev down-dev logs-dev health-dev deploy rollback versions docs clean

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
	$(UV) sync
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

remarkable-pair:  ## Pair this machine with the tablet. Usage: make remarkable-pair CODE=abcd1234
	@if [ -z "$(CODE)" ]; then \
	  echo "Get an 8-character code from my.remarkable.com/device/desktop/connect, then:"; \
	  echo "  make remarkable-pair CODE=<the code>"; \
	  echo "It expires in a few minutes, so fetch it and use it in the same sitting."; \
	  exit 1; fi
	$(PY) scripts/remarkable_pair.py $(CODE)

digest-candidates:  ## What today could contain — the weather, the agenda and the headlines
	$(PY) scripts/call_tool.py digest_list_candidates

digest-dry:  ## Build today's page from PICKS=a-file.json, to out/ and nowhere else
	@test -n "$(PICKS)" || { echo "PICKS=picks.json is required — make digest-candidates first"; exit 1; }
	HARRY_DIGEST_BUILD_OUT_DIR=out $(PY) scripts/call_tool.py digest_build \
	  --args "$$($(PY) -c 'import json,sys; a=json.load(open(sys.argv[1])); a["deliver"]=False; print(json.dumps(a))' $(PICKS))"
	@command -v open >/dev/null && open out/*.pdf || true

# ---------------------------------------------------------------------------
# The container
# ---------------------------------------------------------------------------

# What a build is called. The short commit, because it is the one name that cannot be
# reused for different code — a date can be, twice in an afternoon. A tree that is not
# clean gets `-dirty` appended so it is visibly not a version anybody can go back to, and
# `deploy` refuses one outright.
#
# `git status --porcelain` rather than `git diff HEAD`, which reports clean when the only
# change is an UNTRACKED file. The Dockerfile does `COPY .harry/` and `COPY src/`, so an
# untracked connector or module goes into the image — and would have been tagged with a
# commit it is not in.
DIRTY    = $(shell git status --porcelain 2>/dev/null | head -1)
TAG      = $(shell git rev-parse --short HEAD)$(if $(DIRTY),-dirty,)
DEPLOYED = .deployed-tags
# The tag the real stack runs, newest first. `latest` when nothing has been deployed here,
# which is what makes `make up` work on a machine straight out of a clone.
RUNNING  = $(shell head -1 $(DEPLOYED) 2>/dev/null || echo latest)

image:  ## Build Harry's image, tagged with the commit and as latest
	docker build -t harry:$(TAG) -t harry:latest .
	@echo "  built harry:$(TAG)"

up:  ## Start the real stack on whatever tag is deployed here
	HARRY_TAG=$(RUNNING) docker compose up -d --wait --wait-timeout 120
	@echo "  harry is on harry:$(RUNNING)"

# This service by name, not `docker compose down`: that takes the project's network with
# it and prints "Resource is still in use" whenever the dev stack is up — a line that reads
# like a failure, exits 0 and means nothing.
down:  ## Stop Harry. The data volume is not touched — that needs `docker compose down -v`
	docker compose stop harry
	docker compose rm -f harry

logs:  ## Follow Harry's logs
	docker compose logs -f harry

# Asked from OUTSIDE the container, at the address compose says it published. Reading
# /health by exec-ing in and following $HARRY_PORT would answer the same question the
# image's healthcheck does — and that question was reported healthy while nothing on the
# host could reach Harry at all, because both followed the variable to the same wrong
# place. `docker compose port` is compose's own answer, so nothing here owns the number.
health:  ## What loaded, what did not, and why — asked from the host, the way a caller would
	@ADDR=$$(docker compose port harry 7430 2>/dev/null | head -1); \
	 test -n "$$ADDR" || { echo -e "$(WARN) harry is not running."; exit 1; }; \
	 curl -fsS "http://localhost:$${ADDR##*:}/health" | $(PY) -m json.tool \
	   || { echo -e "$(WARN) harry is up but nothing answered on the port it publishes ($$ADDR)."; exit 1; }

# The dev stack. Separate targets rather than a flag, so nothing that starts, stops or
# rebuilds the real one can reach dev by accident, or the other way round. The `dev`
# profile is what keeps `make up` from starting it at all.

up-dev:  ## Start the dev stack on 7431, with its clock off
	docker compose --profile dev up -d --wait --wait-timeout 120 harry-dev
	@echo "  harry-dev is on harry:latest"

down-dev:  ## Stop the dev stack. The real one is untouched
	docker compose --profile dev stop harry-dev
	docker compose --profile dev rm -f harry-dev

logs-dev:  ## Follow the dev stack's logs
	docker compose --profile dev logs -f harry-dev

health-dev:  ## What the dev stack loaded. `jobs.enabled` is false here, and true on the real one
	@ADDR=$$(docker compose --profile dev port harry-dev 7431 2>/dev/null | head -1); \
	 test -n "$$ADDR" || { echo -e "$(WARN) harry-dev is not running."; exit 1; }; \
	 curl -fsS "http://localhost:$${ADDR##*:}/health" | $(PY) -m json.tool \
	   || { echo -e "$(WARN) harry-dev is up but nothing answered on the port it publishes ($$ADDR)."; exit 1; }

# ---------------------------------------------------------------------------
# Moving versions
# ---------------------------------------------------------------------------
#
# Neither of these touches a volume. The data outlives every deploy and every rollback,
# because the only thing either one changes is which image the container is made from.

deploy:  ## Build this commit, tag it, and put the real stack on it
	@test -z "$(DIRTY)" || { \
	  echo -e "$(WARN) The tree is not clean, so this build could not be rebuilt from git."; \
	  echo "   Commit first. There is no CI here: the tag IS the record of what shipped."; \
	  echo "   Uncommitted or untracked:"; git status --porcelain | sed 's/^/     /'; exit 1; }
	@$(MAKE) --no-print-directory image
	HARRY_TAG=$(TAG) docker compose up -d --wait --wait-timeout 120
	@printf '%s\n' "$(TAG)" > $(DEPLOYED).new
	@grep -vxF "$(TAG)" $(DEPLOYED) 2>/dev/null >> $(DEPLOYED).new || true
	@mv $(DEPLOYED).new $(DEPLOYED)
	@echo -e "$(GREEN)✓ harry is on harry:$(TAG)$(OFF)   (go back with: make rollback)"

rollback:  ## Put the real stack back on the tag it was running before
	@test -s $(DEPLOYED) || { echo -e "$(WARN) Nothing has been deployed here, so there is nothing to go back to."; exit 1; }
	@test "$$(wc -l < $(DEPLOYED))" -ge 2 || { \
	  echo -e "$(WARN) Only one version has been deployed here: harry:$(RUNNING)."; \
	  echo "   Nothing to roll back to."; exit 1; }
	@PREV=$$(sed -n 2p $(DEPLOYED)); \
	 docker image inspect harry:$$PREV >/dev/null 2>&1 || { \
	   echo -e "$(WARN) harry:$$PREV was the previous version and is no longer on this machine."; \
	   echo "   Rebuild it: git checkout $$PREV && make deploy"; exit 1; }
	@PREV=$$(sed -n 2p $(DEPLOYED)); \
	 HARRY_TAG=$$PREV docker compose up -d --wait --wait-timeout 120 && \
	 { sed -n 2p $(DEPLOYED); sed -n 1p $(DEPLOYED); sed -n '3,$$p' $(DEPLOYED); } > $(DEPLOYED).new && \
	 mv $(DEPLOYED).new $(DEPLOYED) && \
	 echo -e "$(GREEN)✓ harry is back on harry:$$PREV$(OFF)   (make rollback again returns to the other one)"

versions:  ## What is deployed here, newest first, and what is still on the machine
	@echo "deployed on this machine, newest first:"; \
	 test -s $(DEPLOYED) && sed 's/^/  /' $(DEPLOYED) || echo "  (nothing yet — make up runs harry:latest)"
	@echo "images still present:"; docker images harry --format '  harry:{{.Tag}}  {{.CreatedSince}}'

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

clean:  ## Remove caches and build output
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov out build dist
	find . -name __pycache__ -type d -prune -exec rm -rf {} +

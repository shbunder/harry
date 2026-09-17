# Harry runs on the NUC, on 24/7, on port 7430.
#
# Two things go in that a plain Python image does not have: the Chromium that
# tier-2 article fetching drives, and the system libraries WeasyPrint renders through.
#
# No `claude` CLI and no model tooling. A Claude scheduled task calls Harry from
# outside; Harry is called, it does not call.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HARRY_PORT=7430 \
    HARRY_DATA_DIR=/data

# WeasyPrint renders through pango and cairo; without these it imports and then
# fails at the first render, which is the worst place to find out.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
        libffi-dev shared-mime-info fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# A virtual display, for the one source that will not answer a headless browser. Measured
# from this image on 2026-09-16 against De Tijd's public homepage: chrome-headless-shell
# 403, full Chromium in headless mode 403, headed Chromium under Xvfb 200. The middle one
# was 200 on 2026-09-13 — the edge tightened in three days, which is the reason to expect
# it to tighten again. `scripts/with-display.sh` starts it for the whole container.
#
# `xauth` because `xvfb-run` — the wrapper anyone reaches for — refuses to start without it
# (`xvfb-run: error: xauth command not found`). With `xvfb` alone the display works only if
# you start `Xvfb` by hand, so the rebuild this block exists to avoid would have happened
# anyway, on the first try.
RUN apt-get update && apt-get install -y --no-install-recommends \
        xvfb xauth \
    && rm -rf /var/lib/apt/lists/*

# Nothing else talks to the tablet. The Go rmapi binary used to be downloaded here for
# one call made once per machine — pairing — and remarkapy turned out to do that itself
# with register_device(code). Two clients would be two reverse-engineered protocol
# implementations to keep working, and twice the surface holding a token that can rewrite
# every document on the device. remarkapy is pinned exactly in pyproject.toml instead.

# No model tooling goes in this image, and no Node to install it with. Harry performs
# heuristic work only — see .claude/rules/no-model-calls.md and ADR-260912-bd36c2.

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv sync --frozen --no-dev

# The browser tier-2 extraction drives. Installed after the deps so a code change
# does not re-download it.
RUN uv run playwright install --with-deps chromium

# `.harry/` holds every connector and job — the product, not configuration. It is
# hidden, which is exactly why it gets its own line and a comment saying so.
COPY .harry/ .harry/
COPY project/ project/
COPY scripts/ scripts/

# Neither `.env` nor `.env.local` is copied in. Compose injects both as real
# environment variables, which outrank the dotenv files anyway — so the image carries no
# configuration and the same image runs on any machine.
VOLUME /data
EXPOSE 7430

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://localhost:{os.environ[\"HARRY_PORT\"]}/health').read()"

# The display De Tijd's browser draws on, started before anything else and then replaced by
# the command — so Harry is still the process `docker stop` signals. `:99` because nothing
# else in this container draws anywhere.
ENV DISPLAY=:99
ENTRYPOINT ["/app/scripts/with-display.sh"]

# `python -m harry`, not a uvicorn command line: the port has one owner, `config.py`.
CMD ["uv", "run", "python", "-m", "harry"]

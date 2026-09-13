# Harry runs on the NUC, on 24/7, on port 7430.
#
# Three things go in that a plain Python image does not have: the Chromium that
# tier-2 article fetching drives, the system libraries WeasyPrint renders through,
# and the `claude` CLI that the 06:30 job invokes over localhost.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HARRY_PORT=7430 \
    HARRY_DATA_DIR=/data

# WeasyPrint renders through pango and cairo; without these it imports and then
# fails at the first render, which is the worst place to find out.
# curl and ca-certificates are for the rmapi download below.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
        libffi-dev shared-mime-info fonts-dejavu-core \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ddvk/rmapi, not juruen/rmapi — the widely-linked one is archived. Pinned exactly:
# the reMarkable protocol is reverse-engineered and a release broke every write in
# August 2026. See .claude/rules/external-sources.md.
ARG RMAPI_VERSION=0.0.35
RUN curl -fsSL "https://github.com/ddvk/rmapi/releases/download/v${RMAPI_VERSION}/rmapi-linuxarm64.tar.gz" \
      -o /tmp/rmapi.tar.gz \
    && tar -xzf /tmp/rmapi.tar.gz -C /usr/local/bin rmapi \
    && rm /tmp/rmapi.tar.gz

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

# `python -m harry`, not a uvicorn command line: the port has one owner, `config.py`.
CMD ["uv", "run", "python", "-m", "harry"]

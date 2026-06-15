FROM python:3.12-slim-bookworm

ENV BUN_INSTALL=/usr/local/bun

# Install uv (Python package/dependency manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY *.py ./
COPY migrations ./migrations
COPY embed ./embed
COPY summerize ./summerize
COPY dependents.json .
COPY ./ts ./ts
COPY ts.sh .

RUN apt-get update \
    && apt-get -y install libpq-dev gcc git ripgrep curl unzip

# Install Bun
RUN curl -fsSL https://bun.sh/install | bash \
    && ln -s $BUN_INSTALL/bin/bun /usr/local/bin/bun

# Install Python dependencies from the lockfile (no dev deps).
RUN uv sync --frozen --no-dev
RUN cd ts && bun install --frozen-lockfile

CMD ["uv", "run", "scraper"]

FROM python:3.12-slim-trixie AS base

COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/

# Copy the project into the image
COPY . /app

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /app

RUN uv --version

# =========================
# Development image
# =========================
FROM base AS dev

RUN uv sync --locked

# Download models for dev
#RUN python -m spacy download en_core_web_sm

COPY . .

CMD ["uv", "run", "main.py", "--reload"]


# =========================
# Production image
# =========================
FROM base AS prod

# Disable development dependencies
ENV UV_NO_DEV=1

RUN uv sync --locked

# Download models at build time to avoid runtime downloads
RUN python -m spacy download en_core_web_sm
# RUN python - <<EOF
# from sentence_transformers import SentenceTransformer
# SentenceTransformer("BAAI/bge-small-en-v1.5")
# EOF

COPY . .

CMD ["uv", "run", "main.py"]

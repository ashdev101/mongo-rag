# Development Guide: Using Docker + UV for RAG Project

This guide is designed for someone using Docker for the first time. It will make development, testing, and dependency management seamless, as if you are developing in a native local Python environment.

---

## 1. Project Setup

### Clone the Repo

```bash
git clone <your-repo-url>
cd <your-repo>
```

### Environment File

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
# Edit .env to add your secrets
```

### Build the Docker Image (First Time)

```bash
docker build -t rag-app:dev .
```

> This will create a Docker image with Python 3.12.3, all dependencies from `uv.lock`, spaCy model, and BAAI embeddings preloaded.

### Running the App

```bash
docker run --rm --env-file .env -p 8000:8000 rag-app:dev
```

You can access the app on `http://localhost:8000` (if applicable).

---

## 2. Development Workflow

We use **volume mounting** so that changes in the code are immediately visible inside the Docker container.

### Start an Interactive Development Shell

```bash
docker run --rm -it --env-file .env -v $(pwd):/app rag-app:dev bash
```

Inside the container, you can run commands as usual:

```bash
# Run the app
uv run python src/app.py

# Run tests
uv run python -m pytest
```

> The `uv run` command ensures the environment is consistent with the locked dependencies.

### Auto-Reload on Code Changes (Optional)

For frameworks like FastAPI:

```bash
uv run uvicorn src.app:app --reload --host 0.0.0.0
```

Volume mounting ensures code changes are reflected immediately without rebuilding the Docker image.

---

## 3. Installing / Updating Dependencies with UV

### Adding a new Python dependency

```bash
# From inside the container or via uv CLI
uv add <package-name>
uv lock
```

Then rebuild the Docker image:

```bash
docker build -t rag-app:dev .
```

### Removing a dependency

```bash
uv remove <package-name>
uv lock
```

> Always update `uv.lock` and rebuild the Docker image to keep consistency.

### Installing a new spaCy model

Inside the container:

```bash
python -m spacy download <model-name>
```

> Prefer pinning the model version in the Dockerfile for reproducibility.

---

## 4. Environment Variables

* Store sensitive keys in `.env` (never commit `.env` to git).
* Docker will pass variables via `--env-file .env`.
* You can also pass individual variables:

```bash
docker run --rm -e OPENAI_API_KEY=xxx rag-app:dev
```

---

## 5. Recommended Commands Cheat Sheet

| Action                             | Command                                                               |
| ---------------------------------- | --------------------------------------------------------------------- |
| Build image                        | `docker build -t rag-app:dev .`                                       |
| Run app                            | `docker run --rm --env-file .env -p 8000:8000 rag-app:dev`            |
| Dev shell                          | `docker run --rm -it --env-file .env -v $(pwd):/app rag-app:dev bash` |
| Run script inside container        | `uv run python src/app.py`                                            |
| Add Python dep                     | `uv add <package>` then `uv lock`                                     |
| Remove Python dep                  | `uv remove <package>` then `uv lock`                                  |
| Run tests                          | `uv run python -m pytest`                                             |
| Run FastAPI dev server with reload | `uv run uvicorn src.app:app --reload --host 0.0.0.0`                  |

---

## 6. Developer Experience Notes

* Developers **do not need Python installed locally**.
* Docker + UV ensures everyone uses the **same environment and dependencies**.
* Changes to Python dependencies must be done using `uv` commands inside the container or via uv CLI on host.
* Code changes are immediately visible in the container due to volume mounts.
* Running tests or scripts uses `uv run` to guarantee consistency.

This workflow ensures a seamless experience: **developers feel like they are working in a local environment, but everything is reproducible, deterministic, and safe inside Docker**.

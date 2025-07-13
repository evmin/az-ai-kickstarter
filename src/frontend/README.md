# Overview

The project is managed via *pyproject.toml* and the
[uv package manager](https://docs.astral.sh/uv/getting-started/installation/).

## Local execution

```bash
# Install the dependencies (creates a .venv automatically)
cd src/frontend
uv sync

# Start Chainlit in watch-mode so that code changes trigger reloads
uv run chainlit run app.py -w
```

## Local configuration

Environment variables are loaded automatically from either the currently selected **azd** environment (`$PROJECT_ROOT/.azure/<env>/.env`) or a local `.env` file. 

See `utils.load_dotenv_from_azd()` for the exact loading logic.

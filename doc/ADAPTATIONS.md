# How to use in different environments

## Using pip for Python requirements 


### Generate requirements.txt files from uv

To generate a `pip`-compatible `requirements.txt` file for the _frontend_
project use the command below. A separate *backend* project no longer exists
in this repository, therefore the corresponding snippet has been removed.


```bash
uv pip compile --project src/frontend src/frontend/pyproject.toml --no-deps | \
    grep -v '# via' | \
    grep -v ipykernel > src/frontend/requirements.txt
```

### Create virtual environments and install

#### Bash/Zsh

```bash
cd src/frontend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### PowerShell

```pwsh
cd src\frontend
python -m venv .venv
. .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Use .env files rather than an AZD environment

Copy the `sample.env` file (if present) in `src/frontend` to `.env` and fill in
the required variables. Optional fields are documented inside the file.

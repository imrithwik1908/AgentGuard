# AgentGuard SDK Publishing

The public Python distribution should use a unique PyPI package name once it is published:

```bash
pip install agentguard-reliability
```

The Python import remains:

```python
from agentguard import AgentGuard
```

## Why not `pip install agentguard`?

The plain `agentguard` name is already used by another PyPI project. Other nearby names such as `agentguard-sdk` are also occupied. A unique distribution name avoids install conflicts while preserving a clean import path.

## Build Locally

From `packages/python-sdk`:

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
```

## Publish To TestPyPI

Requires a TestPyPI account and API token.

```bash
python -m twine upload --repository testpypi dist/*
```

Install from TestPyPI:

```bash
python -m pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  agentguard-reliability
```

## Publish To PyPI

Requires a PyPI account and API token.

```bash
python -m twine upload dist/*
```

After publishing, verify:

```bash
python -m pip install agentguard-reliability
python -c "from agentguard import AgentGuard; print(AgentGuard)"
```

## Before First Public Release

- Replace placeholder project URLs in `packages/python-sdk/pyproject.toml`.
- Add a root `LICENSE` file or update the package license metadata.
- Confirm the public backend URL or document self-hosted setup clearly.
- Run SDK tests and package checks.
- Tag the release in git.

---
status: accepted
date: 2025-01-30
decision-maker: terrylica
consulted: Claude Code agents
research-method: Codebase analysis + Python packaging best practices
---

# Use src-layout Package Structure

## Context and Problem Statement

The crypto-kline-vision-data package needed a professional package structure that:

- Prevents accidental imports from the development directory
- Ensures installed package matches the source exactly
- Follows modern Python packaging standards
- Works correctly with editable installs (`pip install -e .`)

## Decision Drivers

- Prevent test code from accidentally importing from wrong location
- Ensure `python -c "import ckvd"` always loads installed version
- Follow PEP 517/518 build system standards
- Support proper namespace for `ckvd.core.sync.*` imports

## Considered Options

1. **Flat layout** - Package at repository root (`ckvd/`)
2. **src-layout** - Package in `src/` subdirectory (`src/ckvd/`)

## Decision Outcome

Chosen option: **src-layout** because it prevents the common "works in dev, fails in production" issues.

### Consequences

**Good:**

- Running tests from repo root can't accidentally import from source instead of installed package
- Clear separation between package code and project files
- Forces proper editable install for development
- Works correctly with all build backends (setuptools, flit, hatch)

**Bad:**

- Slightly deeper directory structure
- Requires `[tool.setuptools.packages.find] where = ["src"]` configuration

## Implementation

```
crypto-kline-vision-data/
├── src/
│   └── ckvd/      # The actual package
│       ├── __init__.py
│       ├── core/
│       └── utils/
├── tests/                         # Tests live outside src/
├── examples/
└── pyproject.toml
```

pyproject.toml configuration:

```toml
[tool.setuptools.packages.find]
where = ["src"]
include = ["ckvd*"]

[tool.setuptools.package-dir]
"" = "src"
```

## More Information

- [Python Packaging User Guide: src layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
- [Hynek Schlawack: Testing & Packaging](https://hynek.me/articles/testing-packaging/)

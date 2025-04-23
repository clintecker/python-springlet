# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands
- Setup: `make setup`
- Lint: `ruff check .`
- Typecheck: `mypy .`
- Test all: `make test` or `pytest`
- Test single: `pytest tests/path_to_test.py::test_name`
- Run server: `python server/spring83_server.py`
- Run client: `python client/spring83_client.py`
- Deploy: `make deploy`

## Code Style Guidelines
- **Python version**: 3.9+ (standard library only + vendored pure25519)
- **Formatting**: Black, line length 88 characters
- **Linting**: Ruff, flake8
- **Imports**: Stdlib only, alphabetically sorted
- **Naming**: Snake_case for files/functions, PascalCase for classes
- **Types**: Use type hints (PEP 484)
- **Docstrings**: Required, Google style
- **Error handling**: Specific exceptions, descriptive messages
- **Size constraints**: ≤300 LOC server, ≤150 LOC client
- **Testing**: Pytest for unit tests, smoke test for E2E
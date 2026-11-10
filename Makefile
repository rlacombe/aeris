.PHONY: install install-dev test lint clean

# Install the Python package with the local MCP server.
install:
	pip install -e ".[mcp]"

# Install with development dependencies.
install-dev:
	pip install -e ".[mcp,dev]"

# Run tests
test:
	pytest tests/ -v

# Lint
lint:
	ruff check aeris.exposure/ tests/

# Clean build artifacts
clean:
	rm -rf .pytest_cache .ruff_cache

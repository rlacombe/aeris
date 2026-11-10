# AERIS Project Guidelines

## Architecture: Separation of Concerns

- **`aeris.exposure/`** contains the scientific exposure engine: data retrieval, exposure estimation, and quality-control calculations.
- **`aeris.agent/`** contains session state and the CLI-host launcher; **`aeris.mcp/`** exposes the provider-neutral public tool surface.
- Implement scientific operations in `aeris.exposure` and expose them through `aeris.agentic.contract` before adding host-specific behavior.

## Repository

- **Origin**: `rlacombe/aeris` (this fork)
- The repository is self-contained; do not retain an upstream package namespace.

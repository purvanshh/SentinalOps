# Contributing

## Local workflow

1. Copy `.env.example` to `.env`.
2. Start the stack with `make up`.
3. Keep backend Python modules import-clean and use `apply_patch` for targeted edits.
4. Update README and relevant docs when a new phase materially changes architecture or user-facing behavior.

## Expectations

- Preserve evidence-grounded behavior
- Avoid destructive git commands
- Add tests or fixtures when introducing new workflow stages

# SentinelOps Python Style Guide

This document outlines the coding standards and formatting practices enforced across the SentinelOps codebase.

## Formatting & Linting
We use **Ruff** for linting and code formatting, and **Black** for layout formatting. These tools are automatically run via pre-commit hooks and CI.

- **Line Length**: Max 100 characters.
- **Indentation**: 4 spaces (no tabs).
- **Imports**: Sorted and grouped (standard library, third-party, local modules).
- **Type Hints**: Mandatory for all public API routes, core services, and helper functions (Python 3.11 target).

## Running Checks Locally
To ensure your code meets the quality standards before committing:

1. **Format Code**:
   ```bash
   ruff format .
   ```
2. **Lint Code**:
   ```bash
   ruff check . --fix
   ```
3. **Run Pre-Commit Hooks**:
   ```bash
   pre-commit run --all-files
   ```

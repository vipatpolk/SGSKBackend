# SGSKBackend Rules & Quality Assurance Standards

## Mandatory Quality Verification Before Commit/Push
Always run and pass all of the following checks before committing or pushing changes:

1. **Ruff Linter**: `.\.venv\Scripts\ruff.exe check .`
2. **Mypy Type Checker**: `.\.venv\Scripts\mypy.exe .`
   - Strict variable typing: never redeclare variable type annotations inside separate conditional branches (causes `[no-redef]`). Declare types before `if/else` blocks.
3. **Pytest Suite**: `.\.venv\Scripts\pytest.exe -m "not live_e2e"`
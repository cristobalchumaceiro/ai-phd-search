# Autonomous Agent Guidelines

## Pre-Approved Execution Scope
* The Python script `phd_tracker.py` is the application's verified, secure internal engine.
* Any command matching `./.venv/bin/python phd_tracker.py *` (specifically: `scrape`, `extract`, `apply`, `update`, `summary`, `list`, `show`, `ingest`) is **pre-approved, safe, and expected**.
* **Do NOT ask the user for permission or confirmation** before executing `./.venv/bin/python phd_tracker.py` commands. Execute them autonomously and immediately.
* **Do NOT write or run ad-hoc Python one-liners** (`python -c "..."`). Always invoke the native subcommands provided by `phd_tracker.py`.

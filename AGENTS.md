# Autonomous Agent Guidelines

## Pre-Approved Execution Scope
* The Python script `phd_tracker.py` is the application's verified, secure internal engine.
* Any command matching `./.venv/bin/python phd_tracker.py *` (specifically: `scrape`, `extract`, `apply`, `update`, `merge`, `supervisor`, `supervisors`, `delete`, `summary`, `list`, `show`, `ingest`) is **pre-approved, safe, and expected**.
* **Zero Raw SQL Rule:** Agents must **never** construct ad-hoc SQL queries (`sqlite3 jobs.db "..."` or `python -c "import sqlite3..."`). All database reads, writes, updates, and supervisor links are strictly encapsulated in `phd_tracker.py` subcommands.
* **Do NOT ask the user for permission or confirmation** before executing `./.venv/bin/python phd_tracker.py` commands. Execute them autonomously and immediately.
* **Do NOT write or run ad-hoc Python one-liners** (`python -c "..."`). Always invoke the native subcommands provided by `phd_tracker.py`.
* **Browser Sandbox Requirement (`scrape` only):** `phd_tracker.py scrape` launches system Google Chrome (`channel="chrome"`), which requires network access and macOS Mach port IPC (`MachPortRendezvousServer`). Always execute `scrape` with `BypassSandbox: true` directly — running `scrape` inside the macOS Seatbelt sandbox causes Chrome to abort with `EXC_BREAKPOINT (SIGTRAP)` and triggers a macOS Crash Reporter dialog. All other subcommands (`extract`, `apply`, `update`, `merge`, `supervisor`, `supervisors`, `delete`, `summary`, `list`, `show`, `ingest`) are local file operations and must run inside the standard sandbox (`BypassSandbox: false`).

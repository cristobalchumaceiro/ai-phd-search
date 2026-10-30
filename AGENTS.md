# Autonomous Agent Guidelines

## Pre-Approved Execution Scope
* The Python script `ai_phd_search.py` is the application's verified, secure internal engine.
* Any command matching `./.venv/bin/python ai_phd_search.py *` (specifically: `scrape`, `update`, `merge`, `supervisor`, `supervisors`, `delete`, `summary`, `list`, `show`, `ingest`) is **pre-approved, safe, and expected**.
* **Zero Raw SQL Rule:** Agents must **never** construct ad-hoc SQL queries (`sqlite3 jobs.db "..."` or `python -c "import sqlite3..."`). All database reads, writes, updates, and supervisor links are strictly encapsulated in `ai_phd_search.py` subcommands.
* **Zero Temp-File / Zero Ad-Hoc Shell Diagnostics Rule:**
  * Never create or use `tmp/` or `.tmp/` directories in the workspace for matching. All matching and evaluation must inspect listings directly on `stdout` (`list --status unreviewed --full`) and update SQLite directly via `update` and `supervisor`.
  * Never retry any local database command (`list`, `update`, `show`, `summary`, `supervisor`, `merge`, `delete`, `ingest`) with `BypassSandbox: true`.
  * Never run `ps`, `grep`, `kill`, or manual `/Applications/Google Chrome.app` shell commands to debug `scrape`.
* **Do NOT ask the user for permission or confirmation** before executing `./.venv/bin/python ai_phd_search.py` commands. Execute them autonomously and immediately.
* **Do NOT write or run ad-hoc Python one-liners** (`python -c "..."`). Always invoke the native subcommands provided by `ai_phd_search.py`.
* **Browser Sandbox Requirement (`scrape` only):** `ai_phd_search.py scrape` launches system Google Chrome (`channel="chrome"`), which requires network access and macOS Mach port IPC (`MachPortRendezvousServer`). Always execute `scrape` with `BypassSandbox: true` directly — running `scrape` inside the macOS Seatbelt sandbox causes Chrome to abort with `EXC_BREAKPOINT (SIGTRAP)` and triggers a macOS Crash Reporter dialogue. All other subcommands (`update`, `merge`, `supervisor`, `supervisors`, `delete`, `summary`, `list`, `show`, `ingest`) are local file operations and must run inside the standard sandbox (`BypassSandbox: false`).

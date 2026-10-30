# Claude Code Project Guidelines: PhD Tracker

This repository is configured for autonomous AI coding agents.

## Core Rules & Guardrails
* **Pre-Approved Execution Scope:** Any command matching `./.venv/bin/python phd_tracker.py *` (specifically: `scrape`, `update`, `merge`, `supervisor`, `supervisors`, `delete`, `summary`, `list`, `show`, `ingest`) is safe, verified, and pre-approved. Execute these autonomously without prompting the user.
* **Zero Raw SQL Rule:** NEVER execute ad-hoc SQL queries (`sqlite3 jobs.db "..."` or Python scripts importing `sqlite3`). All database interactions are strictly encapsulated within `phd_tracker.py` subcommands.
* **Zero Temp-File / Zero Ad-Hoc Shell Diagnostics Rule:**
  * Never create or use `tmp/` or `.tmp/` directories in the workspace for matching. All matching and evaluation must inspect listings directly on `stdout` (`list --status unreviewed --full`) and update SQLite directly via `update` and `supervisor`.
  * Never retry any local database command (`list`, `update`, `show`, `summary`, `supervisor`, `merge`, `delete`, `ingest`) with `BypassSandbox: true`.
  * Never run `ps`, `grep`, `kill`, or manual `/Applications/Google Chrome.app` shell commands to debug `scrape`.
* **Browser Sandbox Requirement (`scrape` only):** `phd_tracker.py scrape` launches system Google Chrome (`channel="chrome"`) to pass Cloudflare Turnstile verification. Always execute `scrape` with `BypassSandbox: true` directly. All other subcommands are local file operations and must run inside the standard sandbox (`BypassSandbox: false`).

## Agent Workflows & Skills
Detailed agent instructions and lifecycle workflows are located in `.agents/skills/`:
* **Profile Setup (`/phd-tracker setup` or *"Set up my profile"*):** Follow `.agents/skills/phd-tracker/SKILL.md` to interview the user or parse CVs in `docs/` and generate `user_profile.md`.
* **Find New Positions (`/phd-tracker find` or *"Find new positions"*):** Run `./.venv/bin/python phd_tracker.py scrape`, inspect unreviewed listings with `./.venv/bin/python phd_tracker.py list --status unreviewed --full`, score them against `user_profile.md`, update records with `./.venv/bin/python phd_tracker.py update <job_id> [<job_id> ...]`, and present the match digest with `./.venv/bin/python phd_tracker.py list --urgent`.
* **Match Positions (`/phd-tracker match` or *"Match unreviewed jobs"*):** Follow `.agents/skills/phd-tracker/SKILL.md` to evaluate unreviewed positions via `list --status unreviewed --full` and commit decisions directly using `update <job_id> [<job_id> ...]`.
* **Academic Due Diligence (`/phd-researcher <job_id>` or *"Research project <job_id>"*):** Follow `.agents/skills/phd-researcher/SKILL.md` to break down project descriptions, search supervisor publications, suggest foundational reading lists, and record notes.
* **Pipeline Summary (`/phd-tracker summary` or *"Show my summary"*):** Run `./.venv/bin/python phd_tracker.py summary` and `./.venv/bin/python phd_tracker.py list --urgent`.
* **Portal Scraping (`/portal-scraper <url>` or *"Scrape portal"*):** Follow `.agents/skills/portal-scraper/SKILL.md` to scrape bespoke university portals and ingest them via `/tmp/portal_jobs.json`.

## Testing
Verify all changes against the comprehensive test suite:
```bash
./.venv/bin/python -m unittest discover -s tests
```
